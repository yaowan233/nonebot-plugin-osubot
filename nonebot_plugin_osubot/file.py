from io import BytesIO, TextIOWrapper
from typing import Union

import aiohttp
import os
import re
import shutil
import zipfile
from nonebot.log import logger

osufile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'osufile')


async def MapDownload(setid: Union[str, int], DL: bool = False):
    # 判断是否存在该文件
    setid = str(setid)
    if not DL:
        for file in os.listdir(os.path.join(osufile, 'map')):
            if setid == file:
                if os.path.exists(os.path.join(osufile, 'map', file)):
                    return os.path.join(osufile, 'map', file)
    url = f'https://txy1.sayobot.cn/beatmaps/download/novideo/{setid}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=False) as req:
                sayo = req.headers['Location']
    except:
        logger.error('Request Failed or Timeout')
        return
    if DL:
        filename = await OszFileDl(sayo, setid, True)
        return os.path.join(osufile, 'map', filename), filename
    filename = await OszFileDl(sayo, setid)
    filepath = os.path.join(osufile, 'map', filename)
    # 解压下载的osz文件
    myzip = zipfile.ZipFile(filepath)
    mystr = myzip.filename
    print(mystr)
    myzip.extractall(mystr[:-4])
    myzip.close()
    # 删除文件
    removefile(filepath[:-4])
    os.remove(filepath)
    return filepath[:-4]


async def OszFileDl(sayo: str, setid: str, DL: bool = False):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(sayo) as req:
                osufilename = req.content_disposition.filename
                logger.info(f'Start Downloading Map: {osufilename}')
                filename = f'{setid}.osz' if not DL else osufilename
                chunk = await req.read()
                open(os.path.join(osufile, 'map', filename), 'wb').write(chunk)
        logger.info(f'Map: <{osufilename}> Download Complete')
        return filename
    except Exception as e:
        logger.error(f'Map: <{setid}> Download Failed Error:{e}')
        return


async def OsuFileDl(mapid: int):
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
