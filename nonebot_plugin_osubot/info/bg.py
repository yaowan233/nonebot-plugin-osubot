from typing import Union

from nonebot.adapters.onebot.v11 import MessageSegment

from ..api import osu_api
from ..file import map_downloaded, download_osu, re_map


async def get_map_bg(mapid: Union[str, int]) -> Union[str, MessageSegment]:
    info = await osu_api('map', map_id=mapid)
    if not info:
        return '未查询到该地图'
    elif isinstance(info, str):
        return info
    setid: int = info['beatmapset_id']
    dirpath = await map_downloaded(str(setid))
    osu = dirpath / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(setid, mapid)
    path = re_map(osu)
    msg = MessageSegment.image(dirpath / path)
    return msg
