from io import BytesIO, TextIOWrapper
from typing import Union

import aiohttp
import os
import re
import shutil
import zipfile
from pathlib import Path
from nonebot.log import logger

osufile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'osufile')
map_path = Path() / "data" / "osu" / "map"
if not map_path.exists():
    map_path.mkdir(parents=True, exist_ok=True)


async def map_downloaded(setid: str) -> Path:
    # 判断是否存在该文件
    if setid in os.listdir(map_path):
        return map_path / setid
    url = f'https://txy1.sayobot.cn/beatmaps/download/novideo/{setid}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=False) as req:
                sayo = req.headers['Location']
    except Exception as e:
        logger.error(f'Request Failed or Timeout\n{e}')
    filepath = await osz_file_dl(sayo, setid)
    # 解压下载的osz文件
    myzip = zipfile.ZipFile(filepath.absolute())
    myzip.extractall(myzip.filename[:-4])
    myzip.close()
    # 删除文件
    removefile(str(filepath)[:-4])
    os.remove(filepath)
    return map_path / setid


async def download_map(setid: str) -> Path:
    url = f'https://txy1.sayobot.cn/beatmaps/download/novideo/{setid}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=False) as req:
                sayo = req.headers['Location']
    except Exception as e:
        logger.error(f'Request Failed or Timeout\n{e}')
    filepath = await osz_file_dl(sayo, setid, True)
    return filepath


async def osz_file_dl(sayo: str, setid: str, dl: bool = False) -> Path:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(sayo) as req:
                osufilename = req.content_disposition.filename
                logger.info(f'Start Downloading Map: {osufilename}')
                filename = f'{setid}.osz' if not dl else osufilename
                filepath = map_path / filename
                chunk = await req.read()
                open(filepath, 'wb').write(chunk)
        logger.info(f'Map: <{osufilename}> Download Complete')
        return filepath
    except Exception as e:
        logger.error(f'Map: <{setid}> Download Failed Error:{e}')


async def osu_file_dl(mapid: int):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://osu.ppy.sh/osu/{mapid}') as req:
                filename = req.content_disposition.filename
                logger.info(f'Start Downloading .osu File: {filename}')
                osu = await req.read()
        logger.info(f'.osu File: <{filename}> Download Complete')
        return osu
    except Exception as e:
        logger.error(f'.osu File: <{mapid}> Download Failed! Error: {e}')
        return


async def get_projectimg(url: str):
    try:
        if 'avatar-guest.png' in url:
            url = 'https://osu.ppy.sh/images/layout/avatar-guest.png'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as req:
                if req.status == 403:
                    return os.path.join(osufile, 'work', 'mapbg.png')
                data = await req.read()
                im = BytesIO(data)
        return im
    except Exception as e:
        logger.error(f'Image Failed: {e}')
        return e


def removefile(path: str) -> bool:
    bg_list = []
    for file in os.listdir(path):
        if '.osu' in file:
            bg = re_map(os.path.join(path, file))
            if bg not in bg_list:
                bg_list.append(bg)

    for root, dir, files in os.walk(path, topdown=False):
        for name in files:
            if name not in bg_list:
                os.remove(os.path.join(root, name))
        for dirname in dir:
            shutil.rmtree(os.path.join(root, dirname))

    return True


def re_map(file: Union[str, TextIOWrapper]) -> str:
    if isinstance(file, TextIOWrapper):
        text = file.read()
    else:
        text = open(file, 'r', encoding='utf-8').read()
    res = re.search(r'\d,\d,\"(.+)\"', text)
    bg = 'mapbg.png' if not res else res.group(1).strip()
    return bg
