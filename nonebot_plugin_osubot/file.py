from io import BytesIO, TextIOWrapper
from typing import Union, Optional

import re
from pathlib import Path

from nonebot import get_driver
from nonebot.log import logger

from .config import Config
from .api import sayo_api, safe_async_get
from .schema import SayoBeatmap, User, Badge

plugin_config = Config.parse_obj(get_driver().config.dict())


osufile = Path(__file__).parent / "osufile"
map_path = Path() / "data" / "osu" / "map"
user_cache_path = Path() / "data" / "osu" / "user"
badge_cache_path = Path() / "data" / "osu" / "badge"
chimu_api = "https://api.chimu.moe/v1/download/"
kitsu_api = "https://kitsu.moe/api/d/"
sayobot_api = "https://txy1.sayobot.cn/beatmaps/download/novideo/"
api_ls = [sayobot_api, kitsu_api, chimu_api]
download_api = api_ls[plugin_config.osz_mirror]

if not map_path.exists():
    map_path.mkdir(parents=True, exist_ok=True)
if not user_cache_path.exists():
    user_cache_path.mkdir(parents=True, exist_ok=True)
if not badge_cache_path.exists():
    badge_cache_path.mkdir(parents=True, exist_ok=True)


async def download_map(setid: int) -> Optional[Path]:
    url = download_api + str(setid)
    logger.info(f"开始下载地图: <{setid}>")
    req = await safe_async_get(url)
    filename = f"{setid}.osz"
    filepath = map_path.parent / filename
    with open(filepath, "wb") as f:
        f.write(req.read())
    logger.info(f"地图: <{setid}> 下载完毕")
    return filepath


async def download_tmp_osu(map_id):
    url = f"https://osu.ppy.sh/osu/{map_id}"
    logger.info(f"开始下载谱面: <{map_id}>")
    req = await safe_async_get(url)
    filename = f"{map_id}.osu"
    filepath = map_path / filename
    chunk = req.read()
    with open(filepath, "wb") as f:
        f.write(chunk)
    return filepath


async def download_osu(set_id, map_id):
    url = f"https://osu.ppy.sh/osu/{map_id}"
    logger.info(f"开始下载谱面: <{map_id}>")
    req = await safe_async_get(url)
    filename = f"{map_id}.osu"
    filepath = map_path / str(set_id) / filename
    chunk = req.read()
    with open(filepath, "wb") as f:
        f.write(chunk)
    return filepath


async def get_projectimg(url: str):
    if "avatar-guest.png" in url:
        url = "https://osu.ppy.sh/images/layout/avatar-guest.png"
    req = await safe_async_get(url)
    if req.status_code == 403:
        return osufile / "work" / "mapbg.png"
    data = req.read()
    im = BytesIO(data)
    return im


def re_map(file: Union[bytes, Path]) -> str:
    if isinstance(file, bytes):
        text = TextIOWrapper(BytesIO(file), "utf-8").read()
    else:
        with open(file, "r", encoding="utf-8") as f:
            text = f.read()
    res = re.search(r"\d,\d,\"(.+)\"", text)
    bg = "mapbg.png" if not res else res.group(1).strip()
    return bg


async def get_map_id(file: Path) -> str:
    with open(file, "r", encoding="utf-8") as f:
        text = f.read()
    if res := re.search(r"BeatmapID:(\d*)", text):
        return res.group(1).strip()
    res = re.search(r"Version:(.*)\n", text)
    version = res.group(1).strip()
    data = await sayo_api(int(file.parent.name))
    if isinstance(data, str):
        raise Exception(data)
    sayo_info = SayoBeatmap(**data)
    if sayo_info.status == -1:
        raise Exception("未能在sayobot查找到地图信息")
    for map_data in sayo_info.data.bid_data:
        if map_data.version == version:
            return str(map_data.bid)


# 当不存在缓存文件时，建立缓存文件
async def make_user_cache_file(info: User):
    path = user_cache_path / str(info.id)
    path.mkdir()
    user_header = await get_projectimg(info.cover_url)
    user_icon = await get_projectimg(info.avatar_url)
    with open(path / "header.png", "wb") as f:
        f.write(user_header.getvalue())
    with open(path / "icon.png", "wb") as f:
        f.write(user_icon.getvalue())


async def make_badge_cache_file(badge: Badge):
    path = badge_cache_path / f"{hash(badge.description)}.png"
    badge_icon = await get_projectimg(badge.image_url)
    with open(path, "wb") as f:
        f.write(badge_icon.getvalue())


# 保存个人信息界面背景
async def save_info_pic(user: str, url):
    path = user_cache_path / user
    if not path.exists():
        path.mkdir()
    req = await safe_async_get(url)
    with open(path / "info.png", "wb") as f:
        f.write(BytesIO(req.content).getvalue())
