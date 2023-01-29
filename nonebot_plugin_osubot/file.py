from io import BytesIO, TextIOWrapper
from typing import Union, Optional

import aiohttp
import os
import re
import shutil
import zipfile
from pathlib import Path

from nonebot import get_driver
from nonebot.log import logger
from .config import Config

plugin_config = Config.parse_obj(get_driver().config.dict())


osufile = Path(__file__).parent / 'osufile'
map_path = Path() / "data" / "osu" / "map"
chimu_api = 'https://api.chimu.moe/v1/download/'
kitsu_api = 'https://kitsu.moe/api/d/'
sayo_api = 'https://txy1.sayobot.cn/beatmaps/download/novideo/'
api_ls = [sayo_api, kitsu_api, chimu_api]
download_api = api_ls[plugin_config.osz_mirror]

if not map_path.exists():
    map_path.mkdir(parents=True, exist_ok=True)


async def map_downloaded(setid: str) -> Optional[Path]:
    # 判断是否存在该文件
    path = map_path / setid
    if setid in os.listdir(map_path) and list(path.glob('*.osu')):
        return path
    filepath = await download_map(int(setid))
    # 解压下载的osz文件
    try:
        with zipfile.ZipFile(filepath.absolute()) as file:
            file.extractall(file.filename[:-4])
    # 当下载图包失败时自动重试
    except zipfile.BadZipfile:
        return await map_downloaded(setid)
    # 删除文件
    remove_file(Path(str(filepath)[:-4]))
    os.remove(filepath)
    return path


async def download_map(setid: int) -> Optional[Path]:
    url = download_api + str(setid)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as req:
                logger.info(f'Start Downloading Map: <{setid}>')
                filename = f'{setid}.osz'
                filepath = map_path / filename
                chunk = await req.read()
                with open(filepath, 'wb') as f:
                    f.write(chunk)
            logger.info(f'Map: <{setid}> Download Complete')
    except Exception as e:
        logger.error(f'Request Failed or Timeout\n{e}')
    return filepath


async def get_projectimg(url: str):
    try:
        if 'avatar-guest.png' in url:
            url = 'https://osu.ppy.sh/images/layout/avatar-guest.png'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as req:
                if req.status == 403:
                    return osufile / 'work' / 'mapbg.png'
                data = await req.read()
                im = BytesIO(data)
        return im
    except Exception as e:
        logger.error(f'Image Failed: {e}')
        return e


def remove_file(path: Path) -> bool:
    bg_list = set()
    for file in os.listdir(path):
        if '.osu' in file:
            bg = re_map(path / file)
            bg_list.add(bg)
            bid = get_map_id(path / file)
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


def get_map_id(file: Path) -> str:
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()
    res = re.search(r'BeatmapID:(\d*)', text)
    return res.group(1).strip()
