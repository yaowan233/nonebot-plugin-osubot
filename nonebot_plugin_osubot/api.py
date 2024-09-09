import random
from io import BytesIO
from typing import Union, Optional

from nonebot.log import logger
from expiringdict import ExpiringDict
from nonebot import get_plugin_config
from httpx import Response, AsyncClient

from .config import Config
from .network import auto_retry
from .schema import User, SayoBeatmap, RecommendData
from .network.first_response import get_first_response

api = "https://osu.ppy.sh/api/v2"
sayoapi = "https://api.sayobot.cn"
cache = ExpiringDict(max_len=1, max_age_seconds=86400)
plugin_config = get_plugin_config(Config)
proxy = plugin_config.osu_proxy


key = plugin_config.osu_key
client_id = plugin_config.osu_client
bg_url = plugin_config.info_bg


@auto_retry
async def safe_async_get(url, headers: Optional[dict] = None, params: Optional[dict] = None) -> Response:
    async with AsyncClient(proxies=proxy, follow_redirects=True) as client:
        client: AsyncClient
        req = await client.get(url, headers=headers, params=params)
    return req


@auto_retry
async def safe_async_post(url, headers=None, data=None, json=None) -> Response:
    async with AsyncClient(proxies=proxy) as client:
        client: AsyncClient
        req = await client.post(url, headers=headers, data=data, json=json)
    return req


async def renew_token():
    url = "https://osu.ppy.sh/oauth/token"
    if not key or not client_id:
        raise Exception("请设置osu_key和osu_client")
    req = await safe_async_post(
        url,
        json={
            "client_id": f"{client_id}",
            "client_secret": f"{key}",
            "grant_type": "client_credentials",
            "scope": "public",
        },
    )
    if req.status_code == 200:
        osu_token = req.json()
        cache.update({"token": osu_token["access_token"]})
    else:
        logger.error(f"更新OSU token出错 错误{req.status_code}")


async def osu_api(
    project: str,
    uid: int = 0,
    mode: str = "osu",
    map_id: int = 0,
    is_name: bool = False,
    offset: int = 0,
    limit: int = 5,
    legacy_only: int = 0,
) -> Union[str, dict]:
    if is_name:
        info = await get_user_info(f"{api}/users/{uid}?key=username")
        if isinstance(info, str):
            return info
        else:
            uid = info["id"]
    if project == "info" or project == "bind" or project == "update":
        url = f"{api}/users/{uid}/{mode}"
    elif project == "recent":
        url = (
            f"{api}/users/{uid}/scores/recent?mode={mode}&include_fails=1&limit={limit}&offset={offset}"
            f"&legacy_only={legacy_only}"
        )
    elif project == "pr":
        url = f"{api}/users/{uid}/scores/recent?mode={mode}&limit={limit}&offset={offset}&legacy_only={legacy_only}"
    elif project == "score":
        url = f"{api}/beatmaps/{map_id}/scores/users/{uid}/all?mode={mode}"
    elif project == "best_score":
        url = f"{api}/beatmaps/{map_id}/scores/users/{uid}?mode={mode}"
    elif project == "bp":
        url = f"{api}/users/{uid}/scores/best?mode={mode}&limit=100&legacy_only={legacy_only}"
    elif project == "map":
        url = f"{api}/beatmaps/{map_id}"
    else:
        raise "Project Error"
    return await api_info(project, url)


async def sayo_api(setid: int) -> dict:
    url = f"{sayoapi}/v2/beatmapinfo?0={setid}"
    return await api_info("mapinfo", url)


async def get_user_info(url: str) -> Union[dict, str]:
    token = cache.get("token")
    if not token:
        await renew_token()
        token = cache.get("token")
    header = {"Authorization": f"Bearer {token}"}
    req = await safe_async_get(url, headers=header)
    if not req:
        return "api请求失败，请稍后再试"
    if req.status_code == 401:
        await token.update_token()
        return await get_user_info(url)
    elif req.status_code == 404:
        return "未找到该玩家，请确认玩家ID是否正确，有无多余或缺少的空格"
    elif req.status_code == 200:
        return req.json()
    else:
        return "API请求失败，请联系管理员"


async def get_users(users: list[int]):
    token = cache.get("token")
    if not token:
        await renew_token()
        token = cache.get("token")
    headers = {"Authorization": f"Bearer {token}", "x-api-version": "20220705"}
    if req := await safe_async_get(f"{api}/users", headers=headers, params={"ids[]": users}):
        return [User(**i) for i in req.json()["users"]]
    return []


async def api_info(project: str, url: str) -> Union[dict, str]:
    if project == "mapinfo" or project == "PPCalc":
        headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/78.0.3904.108"}
    else:
        token = cache.get("token")
        if not token:
            await renew_token()
            token = cache.get("token")
        headers = {"Authorization": f"Bearer {token}", "x-api-version": "20220705"}
    req = await safe_async_get(url, headers=headers)
    if not req:
        return "api请求失败，请稍后再试"
    if req.status_code >= 400:
        if project == "info" or project == "bind":
            return "未找到该玩家，请确认玩家ID"
        elif project == "recent":
            return "未找到该玩家，请确认玩家ID"
        elif project == "score":
            return "未找到该地图成绩，请检查是否搞混了mapID与setID或模式"
        elif project == "best_score":
            return "未找到该地图成绩，请检查是否搞混了mapID与setID或模式"
        elif project == "bp":
            return "未找到该玩家BP"
        elif project == "map":
            return "未找到该地图，请检查是否搞混了mapID与setID"
        else:
            return "API请求失败，请联系管理员或稍后再尝试"
    return req.json()


async def get_random_bg() -> Optional[bytes]:
    res = await safe_async_get(random.choice(bg_url))
    if res.status_code != 200:
        return
    return res.content


async def get_sayo_map_info(sid, t=0) -> SayoBeatmap:
    res = await safe_async_get(f"https://api.sayobot.cn/v2/beatmapinfo?K={sid}&T={t}")
    return SayoBeatmap(**res.json())


async def get_map_bg(mapid, sid, bg_name) -> BytesIO:
    res = await get_first_response(
        [
            f"https://api.osu.direct/media/background/{mapid}",
            f"https://subapi.nerinyan.moe/bg/{mapid}",
            f"https://dl.sayobot.cn/beatmaps/files/{sid}/{bg_name}",
        ]
    )
    return BytesIO(res)


async def get_seasonal_bg() -> Optional[dict]:
    url = f"{api}/seasonal-backgrounds"
    token = cache.get("token")
    if not token:
        await renew_token()
        token = cache.get("token")
    headers = {"Authorization": f"Bearer {token}"}
    req = await safe_async_get(url, headers=headers)
    if req.status_code != 200:
        return
    return req.json()


async def get_recommend(uid, mode, key_count):
    headers = {"uid": str(uid)}
    params = {
        "newRecordPercent": "0.2,1",
        "passPercent": "0.2,1",
        "difficulty": "0,15",
        "keyCount": key_count,
        "gameMode": mode,
        "rule": "4",
        "current": "1",
        "pageSize": "20",
        "from": "nonebot_plugin_osubot",
        "hidePlayed": "1",
    }
    res = await safe_async_get(
        "https://alphaosu.keytoix.vip/api/v1/self/maps/recommend",
        headers=headers,
        params=params,
    )
    return RecommendData(**res.json())


async def update_recommend(uid):
    headers = {"uid": str(uid)}
    await safe_async_post("https://alphaosu.keytoix.vip/api/v1/self/users/synchronize", headers=headers)
