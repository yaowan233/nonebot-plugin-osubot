import asyncio
from io import BytesIO
from pathlib import Path

from ..api import osu_api
from ..beatmap_stats_moder import with_mods
from ..file import download_osu, map_path
from ..pp import get_ss_pp
from ..schema import Beatmap
from ..schema.score import Mod
from .map_render import duration_text, file_data_uri, remote_image_data_uri, render_map_template


TEMPLATE_PATH = Path(__file__).parent / "map_templates"
MOD_PATH = Path(__file__).parent.parent / "osufile" / "mods"


async def draw_map_info(mapid: int, mods: list[str]) -> BytesIO:
    raw_map = await osu_api("map", map_id=mapid)
    original = Beatmap(**raw_map)
    beatmapset = original.beatmapset
    if beatmapset is None:
        raise ValueError("谱面信息缺少谱面组数据")

    mod_names = [name.upper() for name in mods]
    current = with_mods(original.model_copy(deep=True), None, [Mod(acronym=name) for name in mod_names])
    osu_file = map_path / str(original.beatmapset_id) / f"{mapid}.osu"
    if not osu_file.exists():
        await download_osu(original.beatmapset_id, mapid)

    ss_result = get_ss_pp(str(osu_file.absolute()), original.mode_int, mod_names)
    original_ss_result = get_ss_pp(str(osu_file.absolute()), original.mode_int, [])
    cover, avatar = await asyncio.gather(
        remote_image_data_uri(f"https://assets.ppy.sh/beatmaps/{original.beatmapset_id}/covers/cover@2x.jpg"),
        remote_image_data_uri(f"https://a.ppy.sh/{original.user_id}"),
    )
    mod_images = {
        name: file_data_uri(MOD_PATH / f"{name}.png", "image/png")
        for name in mod_names
        if (MOD_PATH / f"{name}.png").exists()
    }

    payload = {
        "mod_images": mod_images,
        "set": {
            "id": beatmapset.id,
            "title": beatmapset.title,
            "title_unicode": beatmapset.title_unicode,
            "artist": beatmapset.artist,
            "artist_unicode": beatmapset.artist_unicode,
            "creator": beatmapset.creator,
            "user_id": beatmapset.user_id,
            "source": beatmapset.source,
            "status": original.status,
            "ranked_date": (beatmapset.ranked_date or "")[:10].replace("-", "."),
            "favourites": beatmapset.favourite_count,
            "tags": beatmapset.tags.split() if beatmapset.tags else [],
            "cover": cover,
            "avatar": avatar,
        },
        "map": {
            "id": current.id,
            "version": current.version,
            "mode_int": current.mode_int,
            "stars": ss_result.stars,
            "original_stars": original_ss_result.stars,
            "ss_pp": ss_result.pp,
            "bpm": current.bpm or 0,
            "original_bpm": original.bpm or 0,
            "duration": duration_text(current.total_length),
            "max_combo": current.max_combo or 0,
            "objects": current.count_circles + current.count_sliders + current.count_spinners,
            "circles": current.count_circles,
            "sliders": current.count_sliders,
            "spinners": current.count_spinners,
            "plays": current.playcount,
            "passes": current.passcount,
            "mods": [name for name in mod_names if name in mod_images],
            "stats": [
                {"key": "CS", "name": "圆圈大小", "before": original.cs, "after": current.cs},
                {"key": "AR", "name": "接近速度", "before": original.ar, "after": current.ar},
                {"key": "OD", "name": "判定难度", "before": original.accuracy, "after": current.accuracy},
                {"key": "HP", "name": "体力消耗", "before": original.drain, "after": current.drain},
            ],
        },
    }
    return await render_map_template(TEMPLATE_PATH, payload, "map-refined", 960)
