import asyncio
from io import BytesIO
from pathlib import Path

from ..api import get_beatmapsets_info
from ..exceptions import NetworkError
from .map import draw_map_info
from .map_render import duration_text, remote_image_data_uri, render_map_template, beatmap_background_data_uri


TEMPLATE_PATH = Path(__file__).parent / "bmap_templates"
RANKED_STATUS = {
    -2: "graveyard",
    -1: "wip",
    0: "pending",
    1: "ranked",
    2: "approved",
    3: "qualified",
    4: "loved",
}


async def draw_bmap_info(mapid: int) -> BytesIO:
    beatmapset = await get_beatmapsets_info(mapid)
    difficulties = sorted(beatmapset.beatmaps, key=lambda item: item.difficulty_rating)
    if not difficulties:
        raise NetworkError("谱面组中没有可展示的难度")
    if len(difficulties) == 1:
        return await draw_map_info(difficulties[0].id, [])

    cover, avatar = await asyncio.gather(
        beatmap_background_data_uri(
            difficulties[0].id,
            beatmapset.id,
            f"https://assets.ppy.sh/beatmaps/{beatmapset.id}/covers/cover@2x.jpg",
        ),
        remote_image_data_uri(f"https://a.ppy.sh/{beatmapset.user_id}"),
    )
    payload = {
        "set": {
            "id": beatmapset.id,
            "title": beatmapset.title,
            "artist": beatmapset.artist,
            "creator": beatmapset.creator,
            "source": beatmapset.source,
            "bpm": beatmapset.bpm,
            "status": RANKED_STATUS.get(beatmapset.ranked, str(beatmapset.ranked)),
            "ranked_date": (beatmapset.ranked_date or "")[:10].replace("-", ".") or "未上架",
            "favourites": beatmapset.favourite_count,
            "tags": beatmapset.tags,
            "plays": sum(item.playcount for item in difficulties),
            "passes": sum(item.passcount for item in difficulties),
            "cover": cover,
            "avatar": avatar,
            "duration": duration_text(max(item.total_length for item in difficulties)),
        },
        "difficulties": [
            {
                "id": item.id,
                "version": item.version,
                "mode": item.mode_int,
                "stars": item.difficulty_rating,
                "length": duration_text(item.total_length),
                "combo": item.max_combo or 0,
                "cs": item.cs,
                "ar": item.ar,
                "od": item.accuracy,
                "hp": item.drain,
                "plays": item.playcount,
                "passes": item.passcount,
            }
            for item in difficulties
        ],
    }
    visible_count = min(len(difficulties), 20)
    viewport_height = 1000 + max(0, visible_count - 9) * 65
    return await render_map_template(TEMPLATE_PATH, payload, "bmap-refined", viewport_height)
