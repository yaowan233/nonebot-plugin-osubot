import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic

from nonebot.log import logger
from nonebot_plugin_orm import get_session
from httpx import HTTPError
from sqlalchemy import delete, select

from .api import (
    build_oauth_authorize_url,
    exchange_oauth_code,
    get_me_with_token,
    get_oauth_client_id,
    get_oauth_client_secret,
    refresh_oauth_token,
    safe_async_get,
    safe_async_post,
)
from .database import UserData, UserOAuthData
from .exceptions import NetworkError
from .network.manager import network_manager

OAUTH_RELAY_URL = "https://mayumi.xyz/api/osubot/oauth"


class OAuthAuthorizationError(NetworkError):
    pass


class OAuthAccountMismatch(OAuthAuthorizationError):
    pass


@dataclass(frozen=True)
class AuthorizationSession:
    session_id: str
    poll_token: str
    expires_in: int
    redirect_uri: str
    authorize_url: str


def _response_json(response) -> dict:
    try:
        data = response.json()
    except Exception as error:
        raise OAuthAuthorizationError("OAuth 中转站返回了无效响应") from error
    if not isinstance(data, dict):
        raise OAuthAuthorizationError("OAuth 中转站返回了无效响应")
    return data


async def begin_authorization() -> AuthorizationSession:
    """创建一次短期授权会话，并返回用户需要访问的 osu! 授权链接。"""
    if not get_oauth_client_id() or not get_oauth_client_secret():
        raise OAuthAuthorizationError("机器人尚未配置 OSU_CLIENT / OSU_KEY")
    try:
        response = await safe_async_post(f"{OAUTH_RELAY_URL}/sessions")
    except HTTPError as error:
        raise OAuthAuthorizationError("无法连接 OAuth 中转站") from error
    if response is None or response.status_code != 201:
        status = response.status_code if response is not None else "无响应"
        raise OAuthAuthorizationError(f"OAuth 中转站暂时不可用（{status}）")

    data = _response_json(response)
    try:
        session_id = str(data["session_id"])
        poll_token = str(data["poll_token"])
        expires_in = int(data["expires_in"])
        redirect_uri = str(data["redirect_uri"])
    except (KeyError, TypeError, ValueError) as error:
        raise OAuthAuthorizationError("OAuth 中转站返回了不完整的会话") from error
    if not session_id or not poll_token or expires_in <= 0 or not redirect_uri.startswith("https://"):
        raise OAuthAuthorizationError("OAuth 中转站返回了无效会话")

    return AuthorizationSession(
        session_id=session_id,
        poll_token=poll_token,
        expires_in=expires_in,
        redirect_uri=redirect_uri,
        authorize_url=build_oauth_authorize_url(session_id, redirect_uri),
    )


async def wait_for_authorization(session: AuthorizationSession, poll_interval: float = 2.0) -> str:
    """等待中转站收到回调，成功时返回一次性授权码。"""
    deadline = monotonic() + session.expires_in
    headers = {"Authorization": f"Bearer {session.poll_token}"}
    while monotonic() < deadline:
        try:
            response = await safe_async_get(
                f"{OAUTH_RELAY_URL}/sessions/{session.session_id}",
                headers=headers,
            )
        except HTTPError as error:
            raise OAuthAuthorizationError("无法连接 OAuth 中转站") from error
        if response is None:
            raise OAuthAuthorizationError("无法连接 OAuth 中转站")
        if response.status_code == 202:
            await asyncio.sleep(min(poll_interval, max(0.0, deadline - monotonic())))
            continue
        if response.status_code == 410:
            raise OAuthAuthorizationError("授权链接已过期，请重新发送 /friend")
        if response.status_code != 200:
            raise OAuthAuthorizationError(f"OAuth 中转站查询失败（HTTP {response.status_code}）")

        data = _response_json(response)
        if data.get("status") == "complete" and data.get("code"):
            return str(data["code"])
        if data.get("status") == "error":
            raise OAuthAuthorizationError("你取消了 osu! 授权，请重新发送 /friend 后再试")
        raise OAuthAuthorizationError("OAuth 中转站返回了未知状态")
    raise OAuthAuthorizationError("授权链接已过期，请重新发送 /friend")


async def discard_authorization(session: AuthorizationSession) -> None:
    """尽力删除中转站中的会话；失败时由服务端 TTL 自动清理。"""
    try:
        client = await network_manager.get_client()
        await client.delete(
            f"{OAUTH_RELAY_URL}/sessions/{session.session_id}",
            headers={"Authorization": f"Bearer {session.poll_token}"},
        )
    except Exception as error:
        logger.debug(f"清理 OAuth 中转会话失败: {error}")


async def get_valid_oauth(platform_user_id: str) -> UserOAuthData | None:
    """读取与当前 /bind 账号一致的令牌，并在临近过期时刷新。"""
    async with get_session() as session:
        oauth = await session.scalar(select(UserOAuthData).where(UserOAuthData.user_id == platform_user_id))
        bound_osu_id = await session.scalar(select(UserData.osu_id).where(UserData.user_id == platform_user_id))
    if oauth is None or bound_osu_id is None or oauth.osu_id != bound_osu_id:
        return None
    if not oauth.token_expires_at or oauth.token_expires_at > datetime.now() + timedelta(minutes=5):
        return oauth

    try:
        refreshed = await refresh_oauth_token(oauth.refresh_token)
    except (HTTPError, NetworkError) as error:
        logger.warning(f"刷新 OAuth 令牌失败 (osu_id={oauth.osu_id}): {error}")
        return oauth
    oauth.access_token = refreshed.get("access_token", oauth.access_token)
    if refreshed.get("refresh_token"):
        oauth.refresh_token = refreshed["refresh_token"]
    if refreshed.get("expires_in"):
        oauth.token_expires_at = datetime.now() + timedelta(seconds=int(refreshed["expires_in"]))
    async with get_session() as session:
        await session.merge(oauth)
        await session.commit()
    return oauth


async def delete_oauth(platform_user_id: str) -> None:
    """删除失效令牌，使下一次 /friend 自动重新授权。"""
    async with get_session() as session:
        await session.execute(delete(UserOAuthData).where(UserOAuthData.user_id == platform_user_id))
        await session.commit()


async def complete_authorization(
    platform_user_id: str,
    code: str,
    redirect_uri: str,
) -> UserOAuthData:
    """兑换授权码，校验其账号与 /bind 一致，然后持久化令牌。"""
    try:
        token_data = await exchange_oauth_code(code, redirect_uri)
        access_token = token_data.get("access_token")
        if not access_token:
            raise OAuthAuthorizationError("osu! OAuth 响应中缺少 access_token")
        me = await get_me_with_token(access_token)
    except HTTPError as error:
        raise OAuthAuthorizationError("无法连接 osu! OAuth 服务") from error
    authorized_osu_id = int(me["id"])

    async with get_session() as session:
        bound = await session.scalar(select(UserData).where(UserData.user_id == platform_user_id))
        if bound is None:
            raise OAuthAuthorizationError("该账号尚未绑定，请先发送 /bind 用户名")
        if bound.osu_id != authorized_osu_id:
            raise OAuthAccountMismatch(
                f"授权的是 {me['username']}（uid {authorized_osu_id}），"
                f"但当前 /bind 账号是 {bound.osu_name}（uid {bound.osu_id}）。请使用后者重新授权"
            )

        expires_at = None
        if token_data.get("expires_in"):
            expires_at = datetime.now() + timedelta(seconds=int(token_data["expires_in"]))
        oauth = await session.scalar(select(UserOAuthData).where(UserOAuthData.user_id == platform_user_id))
        if oauth is None:
            oauth = UserOAuthData(user_id=platform_user_id)
        oauth.osu_id = authorized_osu_id
        oauth.osu_name = str(me["username"])
        oauth.access_token = access_token
        oauth.refresh_token = token_data.get("refresh_token", oauth.refresh_token if oauth.id else "")
        oauth.token_expires_at = expires_at
        session.add(oauth)
        await session.commit()
        return oauth
