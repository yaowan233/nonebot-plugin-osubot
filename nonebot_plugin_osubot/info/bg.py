from io import BytesIO
from typing import Union
from PIL import Image, UnidentifiedImageError

from ..api import osu_api, get_map_bg
from ..file import download_osu, re_map, map_path


async def get_bg(mapid: Union[str, int]) -> Union[str, BytesIO]:
    info = await osu_api("map", map_id=mapid)
    if not info:
        return "未查询到该地图"
    elif isinstance(info, str):
        return info
    setid: int = info["beatmapset_id"]
    set_path = map_path / str(setid)
    if not set_path.exists():
        set_path.mkdir(parents=True, exist_ok=True)
    osu = map_path / str(setid) / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(setid, mapid)
    cover = re_map(osu)
    cover_path = map_path / str(setid) / cover
    if not cover_path.exists():
        if bg := await get_map_bg(mapid, setid, cover):
            with open(cover_path, "wb") as f:
                f.write(bg.getvalue())
    try:
        img = Image.open(cover_path)
    except UnidentifiedImageError:
        cover_path.unlink()
        return "暂时无法下载背景图片＞︿＜"
    byt = BytesIO()
    img.save(byt, "png")
    return byt
