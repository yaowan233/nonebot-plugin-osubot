from typing import Union

from PIL import Image, UnidentifiedImageError

from ..api import osu_api, get_map_bg
from ..exceptions import NetworkError
from ..file import re_map, map_path, download_osu


async def get_bg(mapid: Union[str, int], setid: int = None) -> Image.Image:
    if not setid:
        info = await osu_api("map", map_id=mapid)
        setid: int = info["beatmapset_id"]
    set_path = map_path / str(setid)
    if not set_path.exists():
        set_path.mkdir(parents=True, exist_ok=True)
    osu = map_path / str(setid) / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(setid, mapid)
    cover = re_map(osu)
    cover_path = map_path / str(setid) / cover
    # Backgrounds are immutable for a beatmap revision. Keep them indefinitely
    # on the hot path, but refresh when checksum validation replaced the .osu
    # file with a newer revision.
    if cover_path.exists() and cover_path.stat().st_mtime_ns < osu.stat().st_mtime_ns:
        cover_path.unlink()
    if not cover_path.exists():
        if bg := await get_map_bg(mapid, setid, cover):
            with open(cover_path, "wb") as f:
                f.write(bg.getvalue())
        else:
            raise NetworkError("暂时无法下载背景图片＞︿＜")
    try:
        img = Image.open(cover_path).convert("RGBA")
    except (UnidentifiedImageError, FileNotFoundError):
        if cover_path.exists():
            cover_path.unlink()
        raise NetworkError("暂时无法下载背景图片＞︿＜")
    return img
