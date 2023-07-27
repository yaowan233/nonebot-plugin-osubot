from io import BytesIO, TextIOWrapper
from typing import Union, Optional

import os
import re
import shutil
import zipfile
from pathlib import Path

from nonebot import get_driver
from nonebot.log import logger

from .config import Config
from .api import sayo_api, safe_async_get
from .schema import SayoBeatmap, User, Badge

plugin_config = Config.parse_obj(get_driver().config.dict())


osufile = Path(__file__).parent / 'osufile'
map_path = Path() / 'data' / 'osu' / 'map'
user_cache_path = Path() / 'data' / 'osu' / 'user'
badge_cache_path = Path() / 'data' / 'osu' / 'badge'
chimu_api = 'https://api.chimu.moe/v1/download/'
kitsu_api = 'https://kitsu.moe/api/d/'
sayobot_api = 'https://txy1.sayobot.cn/beatmaps/download/novideo/'
api_ls = [sayobot_api, kitsu_api, chimu_api]
download_api = api_ls[plugin_config.osz_mirror]

if not map_path.exists():
    map_path.mkdir(parents=True, exist_ok=True)
if not user_cache_path.exists():
    user_cache_path.mkdir(parents=True, exist_ok=True)
if not badge_cache_path.exists():
    badge_cache_path.mkdir(parents=True, exist_ok=True)


async def map_downloaded(setid: str, retry_time=0) -> Optional[Path]:
    # 当重试次数大于三时，报错
    if retry_time > 2:
        raise TimeoutError('osz文件下载失败，请尝试更换其他镜像')
    # 判断是否存在该文件
    path = map_path / setid
    if setid in os.listdir(map_path) and list(path.glob('*.osu')):
        return path
    filepath = await download_map(int(setid))
    # 解压下载的osz文件
    try:
        with zipfile.ZipFile(filepath.absolute()) as file:
            file.extractall(path)
    # 当下载图包失败时自动重试
    except zipfile.BadZipfile:
        return await map_downloaded(setid, retry_time + 1)
    # 删除文件
    await remove_file(path)
    os.remove(filepath)
    return path


async def download_map(setid: int) -> Optional[Path]:
    url = download_api + str(setid)
    logger.info(f'开始下载地图: <{setid}>')
    req = await safe_async_get(url)
    filename = f'{setid}.osz'
    filepath = map_path.parent / filename
    with open(filepath, 'wb') as f:
        f.write(req.read())
    logger.info(f'地图: <{setid}> 下载完毕')
    return filepath


async def download_tmp_osu(map_id):
    url = f'https://osu.ppy.sh/osu/{map_id}'
    logger.info(f'开始下载谱面: <{map_id}>')
    req = await safe_async_get(url)
    filename = f'{map_id}.osu'
    filepath = map_path / filename
    chunk = req.read()
    with open(filepath, 'wb') as f:
        f.write(chunk)
    return filepath


async def download_osu(set_id, map_id):
    url = f'https://osu.ppy.sh/osu/{map_id}'
    logger.info(f'开始下载谱面: <{map_id}>')
    req = await safe_async_get(url)
    filename = f'{map_id}.osu'
    filepath = map_path / str(set_id) / filename
    chunk = req.read()
    with open(filepath, 'wb') as f:
        f.write(chunk)
    return filepath


async def get_projectimg(url: str):
    if 'avatar-guest.png' in url:
        url = 'https://osu.ppy.sh/images/layout/avatar-guest.png'
    req = await safe_async_get(url)
    if req.status_code == 403:
        return osufile / 'work' / 'mapbg.png'
    data = req.read()
    im = BytesIO(data)
    return im


async def remove_file(path: Path) -> bool:
    bg_list = set()
    for file in os.listdir(path):
        if '.osu' in file:
            bg = re_map(path / file)
            bg_list.add(bg)
            bid = await get_map_id(path / file)
            osu_path = path / f'{bid}.osu'
            if osu_path.exists():
                os.remove(osu_path)
                await download_osu(path.name, bid)
            else:
                os.rename(path / file, path / f'{bid}.osu')

    for root, dir, files in os.walk(path, topdown=False):
        for name in files:
            if name not in bg_list and '.osu' not in name:
                os.remove(os.path.join(root, name))
        for dirname in dir:
            shutil.rmtree(os.path.join(root, dirname))
    return True


def re_map(file: Union[bytes, Path]) -> str:
    if isinstance(file, bytes):
        text = TextIOWrapper(BytesIO(file), 'utf-8').read()
    else:
        with open(file, 'r', encoding='utf-8') as f:
            text = f.read()
    res = re.search(r'\d,\d,\"(.+)\"', text)
    bg = 'mapbg.png' if not res else res.group(1).strip()
    return bg


async def get_map_id(file: Path) -> str:
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()
    if res := re.search(r'BeatmapID:(\d*)', text):
        return res.group(1).strip()
    res = re.search(r'Version:(.*)\n', text)
    version = res.group(1).strip()
    data = await sayo_api(int(file.parent.name))
    if isinstance(data, str):
        raise Exception(data)
    sayo_info = SayoBeatmap(**data)
    if sayo_info.status == -1:
        raise Exception('未能在sayobot查找到地图信息')
    for map_data in sayo_info.data.bid_data:
        if map_data.version == version:
            return str(map_data.bid)


# 当不存在缓存文件时，建立缓存文件
async def make_user_cache_file(info: User):
    path = user_cache_path / str(info.id)
    path.mkdir()
    user_header = await get_projectimg(info.cover_url)
    user_icon = await get_projectimg(info.avatar_url)
    with open(path / 'header.png', 'wb') as f:
        f.write(user_header.getvalue())
    with open(path / 'icon.png', 'wb') as f:
        f.write(user_icon.getvalue())


async def make_badge_cache_file(badge: Badge):
    path = badge_cache_path / f'{hash(badge.description)}.png'
    badge_icon = await get_projectimg(badge.image_url)
    with open(path, 'wb') as f:
        f.write(badge_icon.getvalue())


# 保存个人信息界面背景
async def save_info_pic(user: str, url):
    path = user_cache_path / user
    if not path.exists():
        path.mkdir()
    req = await safe_async_get(url)
    with open(path / 'info.png', 'wb') as f:
        f.write(BytesIO(req.content).getvalue())
