import random
from io import BytesIO
from urllib.parse import urlencode
from datetime import datetime, timedelta
from typing import Union, Literal, Optional

from nonebot.log import logger
from expiringdict import ExpiringDict
from nonebot import get_plugin_config
from httpx import Response, AsyncClient

from .utils import FGM
from .config import Config
from .mods import get_mods
from .network import auto_retry
from .exceptions import NetworkError
from .network.first_response import get_first_response
from .schema import User, NewScore, SayoBeatmap, RecommendData
from .schema.score import UnifiedScore, NewStatistics, UnifiedBeatmap
from .schema.ppysb import InfoResponse, ScoresResponse, V2ScoresResponse
from .schema.user import Level, GradeCounts, UnifiedUser, UserStatistics

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
    async with AsyncClient(proxy=proxy, follow_redirects=True) as client:
        req = await client.get(url, headers=headers, params=params)
    return req


@auto_retry
async def safe_async_post(url, headers=None, data=None, json=None) -> Response:
    async with AsyncClient(proxy=proxy) as client:
        req = await client.post(url, headers=headers, data=data, json=json)
    return req


async def renew_token():
    url = "https://osu.ppy.sh/oauth/token"
    if not key or not client_id:
        raise Exception("请设置osu_key和osu_client")
    req = await safe_async_post(
        url,
        json={
            "client_id": client_id,
            "client_secret": key,
            "grant_type": "client_credentials",
            "scope": "public",
        },
    )
    if req and req.status_code == 200:
        osu_token = req.json()
        cache.update({"token": osu_token["access_token"]})
    else:
        logger.error(f"更新OSU token出错 错误{req.status_code}")


async def get_headers() -> dict[str, str]:
    token = cache.get("token")
    if not token:
        await renew_token()
        token = cache.get("token")
    return {"Authorization": f"Bearer {token}", "x-api-version": "20220705"}


async def get_user_scores(
    uid: Union[int, str],
    mode: str,
    scope: str = Literal["recent", "best"],
    source: str = "osu",
    legacy_only: bool = 0,
    include_failed: bool = True,
    offset: int = 0,
    limit: int = 100,
) -> list[UnifiedScore]:
    if source == "osu":
        url = (
            f"{api}/users/{uid}/scores/{scope}?mode={mode}&limit={limit}&legacy_only={int(legacy_only)}"
            f"&offset={offset}&include_fails={int(include_failed)}"
        )
        data = await make_request(url, await get_headers(), "未找到该玩家BP")
        scores = [NewScore(**i) for i in data]
        unified_scores = [
            UnifiedScore(
                mods=i.mods,
                ruleset_id=i.ruleset_id,
                rank=i.rank,
                accuracy=i.accuracy * 100,
                total_score=i.total_score,
                ended_at=datetime.strptime(i.ended_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8),
                max_combo=i.max_combo,
                statistics=i.statistics,
                legacy_total_score=i.legacy_total_score,
                passed=i.passed,
                beatmap=UnifiedBeatmap(
                    id=i.beatmap_id,
                    set_id=i.beatmapset.id,
                    artist=i.beatmapset.artist,
                    title=i.beatmapset.title,
                    version=i.beatmap.version,
                    creator=i.beatmapset.creator,
                    total_length=i.beatmap.total_length,
                    mode=i.beatmap.mode_int,
                    bpm=i.beatmap.bpm,
                    cs=i.beatmap.cs,
                    ar=i.beatmap.ar,
                    hp=i.beatmap.drain,
                    od=i.beatmap.accuracy,
                    stars=i.beatmap.difficulty_rating,
                ),
            )
            for i in scores
        ]
        return unified_scores

    elif source == "ppysb":
        url = f"https://api.ppy.sb/v1/get_player_scores?scope={scope}&id={uid}&mode={FGM[mode]}&limit={limit}&include_failed={int(include_failed)}"
        data = await make_request(url, {}, "未找到该玩家BP")
        data = ScoresResponse(**data)
        # 手动 offset
        filtered_scores = data.scores[offset:]
        return [
            UnifiedScore(
                mods=get_mods(i.mods),
                ruleset_id=i.mode,
                rank=i.grade,
                accuracy=i.acc,
                total_score=i.score,
                ended_at=datetime.strptime(i.play_time, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8),
                max_combo=i.max_combo,
                passed=True,
                statistics=NewStatistics(
                    miss=i.nmiss,
                    perfect=i.ngeki,
                    good=i.nkatu,
                    meh=i.n50,
                    ok=i.n100,
                    great=i.n300,
                    large_tick_hit=i.n100,
                    small_tick_miss=i.nkatu,
                ),
                beatmap=UnifiedBeatmap(
                    id=i.beatmap.id,
                    set_id=i.beatmap.set_id,
                    artist=i.beatmap.artist,
                    title=i.beatmap.title,
                    version=i.beatmap.version,
                    creator=i.beatmap.creator,
                    total_length=i.beatmap.total_length,
                    mode=i.beatmap.mode,
                    bpm=i.beatmap.bpm,
                    cs=i.beatmap.cs,
                    ar=i.beatmap.ar,
                    hp=i.beatmap.hp,
                    od=i.beatmap.od,
                    stars=i.beatmap.diff,
                ),
            )
            for i in filtered_scores
        ]


async def get_user_info_data(uid: Union[int, str], mode: str, source: str = "osu") -> UnifiedUser:
    if source == "osu":
        url = f"{api}/users/{uid}/{mode}"
        data = await make_request(url, await get_headers(), "未找到该玩家，请确认玩家ID")
        return UnifiedUser(**data)

    elif source == "ppysb":
        url = f"https://api.ppy.sb/v1/get_player_info?scope=all&id={uid}"
        data = await make_request(url, {}, "未找到该玩家，请确认玩家ID")
        data = InfoResponse(**data)
        info_data = UnifiedUser(
            avatar_url=f"https://a.ppy.sb/{data.player.info.id}",
            country_code=data.player.info.country.upper(),
            id=data.player.info.id,
            username=data.player.info.name,
            is_supporter=False,
        )
        if mode == "osu":
            info_data.statistics = parse_statistics(data, "0")
        if mode == "taiko":
            info_data.statistics = parse_statistics(data, "1")
        if mode == "fruits":
            info_data.statistics = parse_statistics(data, "2")
        if mode == "mania":
            info_data.statistics = parse_statistics(data, "3")
        if mode == "rxosu":
            info_data.statistics = parse_statistics(data, "4")
        if mode == "rxtaiko":
            info_data.statistics = parse_statistics(data, "5")
        if mode == "rxfruits":
            info_data.statistics = parse_statistics(data, "6")
        if mode == "aposu":
            info_data.statistics = parse_statistics(data, "8")
        return info_data


def parse_statistics(data: InfoResponse, mode):
    return UserStatistics(
        grade_counts=GradeCounts(
            ssh=data.player.stats[mode]["xh_count"],
            ss=data.player.stats[mode]["x_count"],
            sh=data.player.stats[mode]["sh_count"],
            s=data.player.stats[mode]["s_count"],
            a=data.player.stats[mode]["a_count"],
        ),
        hit_accuracy=data.player.stats[mode]["acc"],
        is_ranked=True,
        level=Level(current=100, progress=99),
        maximum_combo=data.player.stats[mode]["max_combo"],
        play_count=data.player.stats[mode]["plays"],
        play_time=data.player.stats[mode]["playtime"],
        pp=data.player.stats[mode]["pp"],
        ranked_score=data.player.stats[mode]["rscore"],
        replays_watched_by_others=0,
        total_hits=data.player.stats[mode]["total_hits"],
        total_score=data.player.stats[mode]["tscore"],
        global_rank=data.player.stats[mode]["rank"],
        country_rank=data.player.stats[mode]["country_rank"],
    )


async def get_ppysb_map_scores(map_md5: str, uid: Union[int, str], mode: str):
    url = f"https://api.ppy.sb/v2/scores?user_id={uid}&mode={FGM[mode]}&map_md5={map_md5}"
    data = await make_request(url, {}, "未找到该玩家成绩")
    data = V2ScoresResponse(**data)
    return [
        UnifiedScore(
            mods=get_mods(i.mods),
            ruleset_id=i.mode,
            rank=i.grade,
            accuracy=i.acc,
            total_score=i.score,
            ended_at=datetime.strptime(i.play_time, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8),
            max_combo=i.max_combo,
            passed=True,
            statistics=NewStatistics(
                miss=i.nmiss,
                perfect=i.ngeki,
                good=i.nkatu,
                meh=i.n50,
                ok=i.n100,
                great=i.n300,
                large_tick_hit=i.n100,
                small_tick_miss=i.nkatu,
            ),
            beatmap=None,
        )
        for i in data.data
    ]


async def osu_api(
    project: str,
    uid: int = 0,
    mode: str = None,
    map_id: int = 0,
    offset: int = 0,
    limit: int = 5,
    legacy_only: int = 0,
) -> dict:
    # 获取用户 ID
    base_url = f"{api}/users/{uid}"
    query_params = {"limit": limit, "offset": offset, "legacy_only": legacy_only}

    if project == "recent":
        endpoint = f"{base_url}/scores/recent"
        query_params["include_fails"] = 1
    elif project == "pr":
        endpoint = f"{base_url}/scores/recent"
    elif project == "score":
        endpoint = f"{api}/beatmaps/{map_id}/scores/users/{uid}/all"
    elif project == "best_score":
        endpoint = f"{api}/beatmaps/{map_id}/scores/users/{uid}"
    elif project == "bp":
        endpoint = f"{base_url}/scores/best"
        query_params["limit"] = 100
    elif project == "map":
        endpoint = f"{api}/beatmaps/{map_id}"
        query_params = {}
    else:
        endpoint = f"{base_url}/{mode}" if mode else base_url
        query_params = {}

    if mode:
        query_params["mode"] = mode

    url = f"{endpoint}?{urlencode(query_params)}" if query_params else endpoint
    return await api_info(project, url)


async def api_info(project: str, url: str) -> dict:
    headers = (
        {"user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/78.0.3904.108"}
        if project in ["mapinfo", "PPCalc"]
        else await get_headers()
    )
    error_messages = {
        "info": "未找到该玩家，请确认玩家ID",
        "bind": "未找到该玩家，请确认玩家ID",
        "recent": "未找到该玩家，请确认玩家ID",
        "score": "未找到该地图成绩，请检查是否搞混了mapID与setID或模式",
        "best_score": "未找到该地图成绩，请检查是否搞混了mapID与setID或模式",
        "bp": "未找到该玩家BP",
        "map": "未找到该地图，请检查是否搞混了mapID与setID",
    }
    return await make_request(url, headers, error_messages.get(project, "API请求失败，请联系管理员或稍后再尝试"))


async def make_request(url: str, headers: dict, error_message: str) -> dict:
    req = await safe_async_get(url, headers=headers)
    if not req:
        raise NetworkError("多次api请求失败，请稍后再试")
    if req.status_code == 404:
        raise NetworkError(error_message)
    elif req.status_code == 200:
        return req.json()
    raise NetworkError(f"出现了未意料的响应码 {req.status_code}")


async def get_uid_by_name(name: str, source: str) -> int:
    if source == "osu":
        info = await get_user_info(f"{api}/users/@{name}")
        return info["id"]
    else:
        url = f"https://api.ppy.sb/v1/get_player_info?scope=all&name={name}"
        data = await make_request(url, {}, "未找到该玩家，请确认玩家ID是否正确")
        return data["player"]["info"]["id"]


async def get_ppysb_uid(name: str) -> int:
    url = f"https://api.ppy.sb/v1/get_player_info?scope=all&name={name}"
    data = await make_request(url, {}, "未找到该玩家，请确认玩家ID是否正确")
    return data["player"]["info"]["id"]


async def get_user_info(url: str) -> dict:
    return await make_request(url, await get_headers(), "未找到该玩家，请确认玩家ID是否正确")


async def get_users(users: list[int]):
    headers = await get_headers()
    req = await safe_async_get(f"{api}/users", headers=headers, params={"ids[]": users})
    return [User(**i) for i in req.json()["users"]] if req else []


async def get_random_bg() -> Optional[bytes]:
    res = await safe_async_get(random.choice(bg_url))
    if res.status_code != 200:
        return None
    return res.content


async def get_sayo_map_info(sid, t=0) -> SayoBeatmap:
    res = await safe_async_get(f"https://api.sayobot.cn/v2/beatmapinfo?K={sid}&T={t}")
    return SayoBeatmap(**res.json())


async def get_map_bg(mapid, sid, bg_name) -> BytesIO:
    res = await get_first_response(
        [
            f"https://osu.direct/api/media/background/{mapid}",
            f"https://subapi.nerinyan.moe/bg/{mapid}",
            f"https://dl.sayobot.cn/beatmaps/files/{sid}/{bg_name}",
        ]
    )
    return BytesIO(res)


async def get_seasonal_bg() -> Optional[dict]:
    url = f"{api}/seasonal-backgrounds"
    headers = await get_headers()
    req = await safe_async_get(url, headers=headers)
    return req.json() if req.status_code == 200 else None


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
