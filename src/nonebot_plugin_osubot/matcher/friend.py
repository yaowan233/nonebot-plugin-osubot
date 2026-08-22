"""好友功能：查询好友列表与互关状态（移植自 yumu-bot 的 !friend / !f）。

用法（触发前缀已改为 /）：
  /friend            查看自己的全部好友列表（无条数上限）
  /friend :pp        按 PP 排序（:acc/:pc/:pt/:th/:t/:u/:c/:n/:o/:m，
                     后缀 + 或 2 表示升序，- 表示降序）
  /friend 1-30       查看第 1-30 位好友
  /friend pp>=300 mutual=true country=JP   组合筛选
  /friend <玩家名>   查询与对方是否互关（mutual）

数据来源：osu! API v2 GET /friends，需要用户级 OAuth 令牌（friends.read）。
每个绑定用户通过 /frbind（或 /bind 提示）完成授权，各自持自己的令牌。
"""

import re
import secrets
from datetime import datetime, timedelta

from expiringdict import ExpiringDict
from nonebot import get_driver, on_command
from nonebot.internal.adapter import Event, Message
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..api import (
    build_oauth_authorize_url,
    exchange_oauth_code,
    get_me_with_token,
    get_oauth_redirect_uri,
    get_osu_user,
    get_user_friends,
    refresh_oauth_token,
    warn_oauth_config,
)
from ..database import UserData, UserOAuthData
from ..draw.friend import draw_friend_list
from ..exceptions import NetworkError

friend = on_command("friend", aliases={"f"}, priority=11, block=True)
frbind = on_command("frbind", aliases={"fb", "好友授权"}, priority=11, block=True)

# OAuth state -> 平台用户 ID 的短期映射（防 CSRF + 回调路由回查）
_oauth_states: ExpiringDict = ExpiringDict(max_len=2000, max_age_seconds=600)


def build_friend_authorize_link(qq: str) -> str:
    """生成指定用户的 osu! OAuth 授权链接；未配置回调地址时返回空串。"""
    try:
        state = secrets.token_urlsafe(16)
        _oauth_states[state] = qq
        return build_oauth_authorize_url(state)
    except NetworkError:
        return ""


# ===========================================================================
# OAuth 令牌管理
# ===========================================================================
async def _get_oauth(qq: str) -> UserOAuthData | None:
    async with get_session() as session:
        return await session.scalar(select(UserOAuthData).where(UserOAuthData.user_id == qq))


async def _ensure_valid_oauth(oauth: UserOAuthData) -> UserOAuthData:
    """令牌临近过期时自动刷新；刷新失败则返回原令牌（调用处报错时再提示重新授权）。"""
    if oauth.token_expires_at and oauth.token_expires_at <= datetime.now() + timedelta(minutes=5):
        try:
            new = await refresh_oauth_token(oauth.refresh_token)
        except NetworkError as e:
            logger.warning(f"刷新 OAuth 令牌失败 (osu_id={oauth.osu_id}): {e}")
            return oauth
        oauth.access_token = new.get("access_token", oauth.access_token)
        if new.get("refresh_token"):
            oauth.refresh_token = new["refresh_token"]
        if new.get("expires_in"):
            oauth.token_expires_at = datetime.now() + timedelta(seconds=int(new["expires_in"]))
        async with get_session() as session:
            await session.merge(oauth)
            await session.commit()
    return oauth


async def _get_valid_oauth(qq: str) -> UserOAuthData | None:
    oauth = await _get_oauth(qq)
    if oauth is None:
        return None
    return await _ensure_valid_oauth(oauth)


async def _complete_oauth(code: str, state: str | None = None, qq: str | None = None) -> str:
    """授权码 -> 令牌 -> 存库。state 优先（回调路由），否则用传入的 qq（手动 /frbind <code>）。"""
    if qq is None:
        qq = _oauth_states.get(state) if state else None
    if not qq:
        return "授权链接无效或已过期，请重新发送 /frbind 获取新链接。"
    try:
        token_data = await exchange_oauth_code(code)
        access_token = token_data.get("access_token")
        if not access_token:
            return "OAuth 授权失败：响应中缺少 access_token，请重新发送 /frbind 重试。"
        me = await get_me_with_token(access_token)
    except NetworkError as e:
        logger.error(f"OAuth 授权失败 (qq={qq}): {e}")
        msg = str(e)
        if "invalid_client" in msg:
            hint = (
                "osu! 拒绝了 client_id/client_secret（凭据认证失败）。\n"
                "请检查 osu_oauth_client_id / osu_oauth_client_secret（或 osu_client / osu_key）"
                "配置是否正确，修改后需重启 bot。"
            )
        elif "invalid_grant" in msg or "invalid_request" in msg:
            hint = "授权码无效、已过期或已被使用，请重新发送 /frbind 获取新链接重新授权。"
        else:
            hint = ""
        return f"OAuth 授权失败：{e}\n{hint}\n请重新发送 /frbind 重试。"

    expires_at = None
    if token_data.get("expires_in"):
        expires_at = datetime.now() + timedelta(seconds=int(token_data["expires_in"]))

    async with get_session() as session:
        oauth = await session.scalar(select(UserOAuthData).where(UserOAuthData.user_id == qq))
        if oauth is None:
            oauth = UserOAuthData(
                user_id=qq,
                osu_id=int(me["id"]),
                osu_name=me["username"],
                access_token=access_token,
                refresh_token=token_data.get("refresh_token", ""),
                token_expires_at=expires_at,
            )
        else:
            oauth.osu_id = int(me["id"])
            oauth.osu_name = me["username"]
            oauth.access_token = access_token
            if token_data.get("refresh_token"):
                oauth.refresh_token = token_data["refresh_token"]
            oauth.token_expires_at = expires_at
        session.add(oauth)
        await session.commit()

    return (
        f"OAuth 授权成功！已绑定 osu! 账号 {me['username']}（uid {me['id']}）。\n"
        "现在可以发送 /friend 查看好友列表，或 /friend <玩家名> 查询互关状态。"
    )


# ===========================================================================
# /frbind：OAuth 授权
# ===========================================================================
def _extract_oauth_code(text: str) -> str:
    """从用户粘贴的内容中提取授权码 code。

    兼容三种粘贴形式：
      1. 完整回调地址:  https://.../osubot/oauth/callback?code=XXXX&state=YYYY
      2. query 片段:    code=XXXX&state=YYYY
      3. 裸授权码:      XXXX（可能误带 &state 尾巴，自动截断）
    """
    text = (text or "").strip()
    if not text:
        return ""
    # 1. 完整 URL → 解析 query 参数
    if text.startswith(("http://", "https://")):
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(text).query)
        return qs.get("code", [""])[0]
    # 2. 含 code= 的片段 → 取 code= 之后、& 之前
    if "code=" in text:
        after = text.split("code=")[-1]
        return after.split("&")[0]
    # 3. 裸授权码 → 截掉可能的 &state 尾巴
    return text.split("&")[0]


@frbind.handle()
async def _frbind(event: Event, arg: Message = CommandArg()):
    qq = event.get_user_id()
    text = arg.extract_plain_text().strip()

    # 手动粘贴授权码/回调地址：/frbind <code> 或 /frbind <完整网址>
    if text:
        code = _extract_oauth_code(text)
        if not code:
            await frbind.finish(
                "未识别到授权码，请把授权后地址栏里 code= 后面的内容（或完整网址）发给我：/frbind <code>"
            )
        await frbind.finish(await _complete_oauth(code, qq=qq))

    try:
        redirect_uri = get_oauth_redirect_uri()
    except NetworkError as e:
        await frbind.finish(str(e))

    oauth = await _get_oauth(qq)
    prefix = ""
    if oauth:
        prefix = f"你已授权过 osu! 账号 {oauth.osu_name}（uid {oauth.osu_id}），重新授权将覆盖旧令牌。\n"

    state = secrets.token_urlsafe(16)
    _oauth_states[state] = qq
    url = build_oauth_authorize_url(state)
    await frbind.finish(
        f"{prefix}请点击以下链接完成 osu! OAuth 授权（用于查询好友/互关）：\n{url}\n\n"
        "授权完成后会自动回调绑定，无需任何操作。\n"
        "如果无法自动回调（比如回调地址不可达），授权后浏览器地址栏会出现 "
        "…/osubot/oauth/callback?code=XXXX&state=…，\n"
        "把【整个网址】或【code= 后面、& 前面的那串】发给机器人即可：\n"
        "/frbind <code>\n"
        "（直接粘贴完整网址也可以，无需手动去掉 &state 部分）"
    )


# ===========================================================================
# /friend：好友列表 / 互关查询
# ===========================================================================
@friend.handle()
async def _friend(event: Event, arg: Message = CommandArg()):
    qq = event.get_user_id()

    async with get_session() as session:
        user_data = await session.scalar(select(UserData).where(UserData.user_id == qq))
    if not user_data:
        await friend.finish("该账号尚未绑定，请输入 /bind 用户名 绑定账号")
    oauth = await _get_valid_oauth(qq)
    if oauth is None:
        # 已 /bind 但未授权：直接给出授权链接（回调地址未配置时退化为独立提示）
        url = build_friend_authorize_link(qq)
        if url:
            await friend.finish(
                "已完成 /bind 绑定，还需完成 osu! OAuth 授权后才能查询好友。\n"
                f"请点击以下链接授权：\n{url}\n"
                "（若无法自动回调，把授权后地址栏里 code= 后面的内容发给机器人：/frbind <code>）"
            )
        await friend.finish(
            "已完成 /bind 绑定，但尚未完成 osu! OAuth 授权，无法获取好友列表。\n"
            "请发送 /frbind 完成授权后再试（若提示未配置，需先设置 osu_oauth_redirect_uri）。"
        )

    text = arg.extract_plain_text().strip()
    sort_type, sort_direction, text = _parse_sort(text)
    range_match = re.match(r"#?\s*(\d+)(?:\s*-\s*(\d+))?", text)
    start = end = None
    if range_match and range_match.start() == 0:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else start
        text = text[range_match.end() :].strip()

    conditions, rest = _parse_conditions(text)

    try:
        friends = await get_user_friends(oauth.access_token)
    except NetworkError as e:
        await friend.finish(
            f"无法获取好友列表：{e}\n"
            "若授权已失效，请重新授权（发送 /frbind 获取授权链接，或重新点击 /bind 回复中的授权链接）。"
        )

    # 玩家名模式：查询互关
    if rest:
        await _handle_pair(oauth, friends, rest)
        return

    # 列表模式
    if not friends:
        await friend.finish("你的好友列表还是空的哦～")

    sorted_friends = _sort_friends(friends, sort_type, sort_direction)
    filtered = _filter_friends(sorted_friends, conditions)
    if not filtered:
        await friend.finish("没有找到符合条件的好友，试试调整筛选条件吧")
    total = len(filtered)

    # 取消单指令条数上限：未显式指定范围时默认展示全部好友
    start = start or 1
    end = end or total
    if end < start:
        start, end = end, start  # 反向范围自动纠正
    end = min(end, total)

    selected = filtered[start - 1 : end]
    if not selected:
        await friend.finish(f"好友数量不足，当前符合条件的好友共 {total} 位。")

    try:
        img = await draw_friend_list(
            {
                "me_name": oauth.osu_name,
                "me_avatar": f"https://a.ppy.sh/{oauth.osu_id}",
                "sort_label": _sort_label(sort_type, sort_direction),
                "total": total,
                "start": start,
                "end": start + len(selected) - 1,
                "friends": [
                    {
                        "avatar": f.target.avatar_url,
                        "name": f.target.username,
                        "uid": f.target_id,
                        "country": (f.target.country_code or "")[:2],
                        "online": f.target.is_online,
                        "mutual": f.mutual,
                        "supporter": f.target.is_supporter,
                    }
                    for f in selected
                ],
            }
        )
    except Exception as e:
        logger.opt(exception=e).error("渲染好友列表失败")
        await friend.finish(f"渲染好友列表失败：{e}")
    await UniMessage.image(raw=img).finish(reply_to=True)


async def _handle_pair(oauth: UserOAuthData, friends: list, name_text: str) -> None:
    """互关查询：/friend <玩家名>"""
    try:
        partner = await get_osu_user(name_text)
    except NetworkError as e:
        await friend.finish(f"在 osu! 服务器没有找到玩家: {name_text}（{e}）")
    partner_id = int(partner["id"])
    partner_name = partner["username"]

    if partner_id == oauth.osu_id:
        await friend.finish("你自己与你自己就是最好的朋友。")

    my_following = next((f for f in friends if f.target_id == partner_id), None)

    # 若对方也完成了 OAuth 授权，可精确判断对方是否关注我
    partner_followed_me: bool | None = None
    partner_friend_count: int | None = None
    async with get_session() as session:
        partner_oauth = await session.scalar(select(UserOAuthData).where(UserOAuthData.osu_id == partner_id))
    if partner_oauth is not None:
        try:
            partner_oauth = await _ensure_valid_oauth(partner_oauth)
            partner_friends = await get_user_friends(partner_oauth.access_token)
            partner_friend_count = len(partner_friends)
            partner_followed_me = any(f.target_id == oauth.osu_id for f in partner_friends)
        except Exception:
            partner_followed_me = None
    elif my_following is not None:
        # 对方未授权时，用我这边好友条目的 mutual 标记推断
        partner_followed_me = my_following.mutual

    if my_following is not None:
        if partner_followed_me:
            text_msg = f"恭喜！你已经与 {partner_name} 互相成为好友了（mutual）。"
        else:
            text_msg = f"你已经添加了 {partner_name} 作为你的好友，但对方似乎还没有添加你。"
    elif partner_followed_me is None:
        text_msg = f"你还没有将 {partner_name} 添加为你的好友，并且对方没有完成 OAuth 授权，还不知道有没有添加你。"
    elif partner_followed_me:
        text_msg = f"你还没有将 {partner_name} 添加为你的好友，但对方似乎已经悄悄添加了你。"
    else:
        text_msg = "你们暂未互相成为好友。或许可以考虑一下？"

    extra = f"\n你的好友数：{len(friends)}"
    if partner_friend_count is not None:
        extra += f" ｜ {partner_name} 的好友数：{partner_friend_count}"
    await friend.finish(text_msg + extra)


# ===========================================================================
# 排序 / 筛选
# ===========================================================================
_SORT_SPECS = {
    "p": ("pp", "desc"),
    "pp": ("pp", "desc"),
    "performance": ("pp", "desc"),
    "p+": ("pp", "asc"),
    "pp+": ("pp", "asc"),
    "p2": ("pp", "asc"),
    "pp2": ("pp", "asc"),
    "a": ("acc", "desc"),
    "acc": ("acc", "desc"),
    "accuracy": ("acc", "desc"),
    "a+": ("acc", "asc"),
    "acc+": ("acc", "asc"),
    "a2": ("acc", "asc"),
    "acc2": ("acc", "asc"),
    "pc": ("pc", "desc"),
    "playcount": ("pc", "desc"),
    "pc+": ("pc", "asc"),
    "pc2": ("pc", "asc"),
    "playcount+": ("pc", "asc"),
    "pt": ("pt", "desc"),
    "playtime": ("pt", "desc"),
    "pt+": ("pt", "asc"),
    "pt2": ("pt", "asc"),
    "th": ("th", "desc"),
    "h": ("th", "desc"),
    "tth": ("th", "desc"),
    "totalhits": ("th", "desc"),
    "th+": ("th", "asc"),
    "h+": ("th", "asc"),
    "th2": ("th", "asc"),
    "t": ("time", "asc"),
    "time": ("time", "asc"),
    "seen": ("time", "asc"),
    "t-": ("time", "desc"),
    "time-": ("time", "desc"),
    "t2": ("time", "desc"),
    "u": ("uid", "asc"),
    "uid": ("uid", "asc"),
    "u-": ("uid", "desc"),
    "uid-": ("uid", "desc"),
    "c": ("country", "asc"),
    "country": ("country", "asc"),
    "c-": ("country", "desc"),
    "n": ("name", "asc"),
    "name": ("name", "asc"),
    "n-": ("name", "desc"),
    "o": ("online", "true"),
    "on": ("online", "true"),
    "online": ("online", "true"),
    "o-": ("online", "false"),
    "off": ("online", "false"),
    "offline": ("online", "false"),
    "m": ("mutual", "true"),
    "mu": ("mutual", "true"),
    "mutual": ("mutual", "true"),
    "m-": ("mutual", "false"),
    "single": ("mutual", "false"),
}

_SORT_LABELS = {
    "pp": "PP",
    "acc": "ACC",
    "pc": "游玩次数",
    "pt": "游玩时长",
    "th": "总击打",
    "time": "最后上线",
    "uid": "UID",
    "country": "国家/地区",
    "name": "名字",
    "online": "在线",
    "mutual": "互关",
}


def _parse_sort(text: str) -> tuple[str | None, str | None, str]:
    """解析开头的 :xxx 排序标记。返回 (sort_type, direction, 剩余文本)。"""
    m = re.match(r":\s*([\w+\-]+)", text)
    if not m:
        return None, None, text
    key = m.group(1).strip().lower()
    spec = _SORT_SPECS.get(key)
    if spec is None:
        # 未识别的排序标记视为玩家名的一部分（如 :mode），直接透传
        return None, None, text
    return spec[0], spec[1], text[m.end() :].strip()


def _sort_friends(friends: list, sort_type: str | None, direction: str | None) -> list:
    """按 yumu-bot 语义排序；无排序时按名字升序（确定性输出）。"""
    if sort_type is None:
        return sorted(friends, key=lambda f: (f.target.username or "").lower())

    def pp(f):
        return (
            f.target.statistics.pp if f.target and f.target.statistics and f.target.statistics.pp is not None else 0.0
        )

    def acc(f):
        return (
            f.target.statistics.hit_accuracy
            if f.target and f.target.statistics and f.target.statistics.hit_accuracy is not None
            else 0.0
        )

    def num(key):
        def getter(f):
            stats = f.target.statistics if f.target else None
            if stats is None:
                return 0
            return {
                "pc": stats.play_count,
                "pt": stats.play_time,
                "th": stats.total_hits,
            }.get(key, 0) or 0

        return getter

    def last_visit(f):
        if f.target and f.target.last_visit:
            try:
                return datetime.fromisoformat(f.target.last_visit.replace("Z", "+00:00"))
            except ValueError:
                return datetime.min
        return datetime.min

    reverse = direction == "desc"

    if sort_type == "pp":
        return sorted(friends, key=pp, reverse=reverse)
    if sort_type == "acc":
        return sorted(friends, key=acc, reverse=reverse)
    if sort_type in ("pc", "pt", "th"):
        return sorted(friends, key=num(sort_type), reverse=reverse)
    if sort_type == "time":
        return sorted(friends, key=last_visit, reverse=reverse)
    if sort_type == "uid":
        return sorted(friends, key=lambda f: f.target_id, reverse=reverse)
    if sort_type == "country":
        return sorted(
            friends,
            key=lambda f: (f.target.country_code or "") if f.target else "",
            reverse=reverse,
        )
    if sort_type == "name":
        return sorted(friends, key=lambda f: (f.target.username or "").lower(), reverse=reverse)
    if sort_type == "online":
        online = [f for f in friends if f.target and f.target.is_online]
        offline = [f for f in friends if not (f.target and f.target.is_online)]
        return online + offline if direction != "false" else offline
    if sort_type == "mutual":
        mutual = [f for f in friends if f.mutual]
        others = [f for f in friends if not f.mutual]
        return mutual + others if direction != "false" else others
    return sorted(friends, key=lambda f: (f.target.username or "").lower())


def _sort_label(sort_type: str | None, direction: str | None) -> str:
    if sort_type is None:
        return "默认"
    label = _SORT_LABELS.get(sort_type, sort_type)
    if sort_type in ("online", "mutual"):
        return f"{label}：{'只看' if direction == 'true' else '排除'}"
    return f"{label}{' ↑' if direction == 'asc' else ' ↓' if direction == 'desc' else ''}"


_CONDITION_PATTERN = re.compile(r'(\w+)\s*(!=|>=|<=|~=|~|=|>|<)\s*("[^"]*"|\'[^\']*\'|\S+)')

_FIELD_MAP = {
    "name": "username",
    "username": "username",
    "user": "username",
    "n": "username",
    "id": "id",
    "uid": "id",
    "i": "id",
    "country": "country",
    "code": "country",
    "c": "country",
    "mutual": "mutual",
    "mu": "mutual",
    "m": "mutual",
    "online": "online",
    "on": "online",
    "o": "online",
    "active": "active",
    "e": "active",
    "bot": "bot",
    "b": "bot",
    "deleted": "deleted",
    "del": "deleted",
    "d": "deleted",
    "supporter": "supporter",
    "vip": "supporter",
    "v": "supporter",
    "pp": "pp",
    "p": "pp",
    "performance": "pp",
    "acc": "acc",
    "accuracy": "acc",
    "a": "acc",
    "pc": "pc",
    "playcount": "pc",
    "pt": "pt",
    "playtime": "pt",
    "th": "th",
    "h": "th",
    "tth": "th",
    "totalhits": "th",
    "level": "level",
    "lv": "level",
    "l": "level",
    "combo": "max_combo",
    "cb": "max_combo",
    "rank": "global_rank",
    "ranking": "global_rank",
    "k": "global_rank",
    "ssh": "ssh",
    "ss": "ss",
    "sh": "sh",
    "s": "s",
    "ra": "a",
}


def _parse_conditions(text: str) -> tuple[list[tuple[str, str, str]], str]:
    """解析筛选条件，返回 (条件列表, 剩余文本)。条件从原文中剔除，剩余部分视为玩家名。"""
    conditions: list[tuple[str, str, str]] = []

    def _repl(match: re.Match) -> str:
        key, op, value = match.group(1), match.group(2), match.group(3).strip("\"'")
        field = _FIELD_MAP.get(key.lower())
        if field:
            conditions.append((field, op, value))
        return " "

    remaining = _CONDITION_PATTERN.sub(_repl, text)
    return conditions, remaining.strip()


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "y", "是", "对"}


def _match_value(operator: str, expected: str, actual) -> bool:
    if operator in (">", ">=", "<", "<=", "=", "!=") and isinstance(actual, (int, float)):
        try:
            expected_num = float(expected)
        except ValueError:
            return False
        if operator == "=":
            return actual == expected_num
        if operator == "!=":
            return actual != expected_num
        if operator == ">":
            return actual > expected_num
        if operator == ">=":
            return actual >= expected_num
        if operator == "<":
            return actual < expected_num
        if operator == "<=":
            return actual <= expected_num
    if operator == "=":
        return str(actual).lower() == expected.lower()
    if operator == "!=":
        return str(actual).lower() != expected.lower()
    if operator == "~":
        return expected.lower() in str(actual).lower()
    if operator == "~=":
        from difflib import SequenceMatcher

        return SequenceMatcher(None, str(actual).lower(), expected.lower()).ratio() >= 0.5
    return False


def _filter_friends(friends: list, conditions: list[tuple[str, str, str]]) -> list:
    result = friends
    for field, op, value in conditions:
        filtered = []
        for f in result:
            stats = f.target.statistics if f.target else None
            if field == "username":
                actual = (f.target.username if f.target else "") or ""
            elif field == "id":
                actual = f.target_id
            elif field == "country":
                actual = (f.target.country_code if f.target else "") or ""
            elif field in ("mutual", "online", "active", "bot", "deleted", "supporter"):
                # 布尔字段：= 与 != 直接比较解析后的布尔值
                if field == "mutual":
                    actual = bool(f.mutual)
                else:
                    actual = bool(f.target and getattr(f.target, f"is_{field}", False))
                expected_bool = _as_bool(value)
                if (op == "=" and actual == expected_bool) or (op == "!=" and actual != expected_bool):
                    filtered.append(f)
                continue
            elif field == "pp":
                actual = stats.pp if stats and stats.pp is not None else 0.0
            elif field == "acc":
                actual = stats.hit_accuracy if stats and stats.hit_accuracy is not None else 0.0
            elif field == "pc":
                actual = stats.play_count if stats else 0
            elif field == "pt":
                actual = stats.play_time if stats else 0
            elif field == "th":
                actual = stats.total_hits if stats else 0
            elif field == "level":
                actual = stats.level.current if stats and stats.level else 0
            elif field == "max_combo":
                actual = stats.maximum_combo if stats else 0
            elif field == "global_rank":
                actual = stats.global_rank if stats and stats.global_rank is not None else 0
            elif field == "ssh":
                actual = stats.grade_counts.ssh if stats and stats.grade_counts else 0
            elif field == "ss":
                actual = stats.grade_counts.ss if stats and stats.grade_counts else 0
            elif field == "sh":
                actual = stats.grade_counts.sh if stats and stats.grade_counts else 0
            elif field == "s":
                actual = stats.grade_counts.s if stats and stats.grade_counts else 0
            elif field == "a":
                actual = stats.grade_counts.a if stats and stats.grade_counts else 0
            else:
                continue
            if _match_value(op, value, actual):
                filtered.append(f)
        result = filtered
    return result


# ===========================================================================
# OAuth 回调路由（FastAPI / Quart 驱动可自动挂载）
# ===========================================================================
def _register_callback_route() -> None:
    driver = get_driver()
    if driver.type not in ("fastapi", "quart"):
        logger.warning(f"当前驱动 {driver.type} 无法自动挂载 OAuth 回调路由；用户可通过 /frbind <code> 手动完成授权")
        return
    app = driver.server_app
    try:
        redirect_uri = get_oauth_redirect_uri()
    except NetworkError:
        logger.info("未配置 osu_oauth_redirect_uri，暂不挂载 OAuth 回调路由")
        return

    if driver.type == "fastapi":
        from fastapi import Request as FastAPIRequest

        async def _callback(request: FastAPIRequest):
            from fastapi.responses import PlainTextResponse

            msg = await _complete_oauth(
                request.query_params.get("code", ""),
                request.query_params.get("state"),
            )
            return PlainTextResponse(msg)

        app.add_api_route("/osubot/oauth/callback", _callback, methods=["GET"])
    else:  # quart
        from quart import request as quart_request

        async def _callback():
            msg = await _complete_oauth(
                quart_request.args.get("code", ""),
                quart_request.args.get("state"),
            )
            return msg

        app.add_url_rule("/osubot/oauth/callback", "osubot_oauth_callback", _callback, methods=["GET"])

    logger.info(f"OAuth 回调路由已挂载：/osubot/oauth/callback（回调地址 {redirect_uri}）")


_register_callback_route()
warn_oauth_config()
