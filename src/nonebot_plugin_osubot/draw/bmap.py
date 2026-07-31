import asyncio
from io import BytesIO
from pathlib import Path

from ..api import get_beatmapsets_info
from ..exceptions import NetworkError
from ..schema.beatmap import Gds
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


async def _avatar_data_uri(user_id: int) -> str:
    try:
        return await asyncio.wait_for(remote_image_data_uri(f"https://a.ppy.sh/{user_id}"), timeout=8)
    except Exception:
        return f"https://a.ppy.sh/{user_id}"


def _has_different_owners(owner_groups: list[list[Gds]]) -> bool:
    return len({tuple(sorted(owner.id for owner in owners)) for owners in owner_groups}) > 1


async def draw_bmap_info(mapid: int) -> BytesIO:
    beatmapset = await get_beatmapsets_info(mapid)
    difficulties = sorted(beatmapset.beatmaps, key=lambda item: item.difficulty_rating)
    if not difficulties:
        raise NetworkError("谱面组中没有可展示的难度")
    if len(difficulties) == 1:
        return await draw_map_info(difficulties[0].id, [])

    difficulty_owners = [
        item.owners or [Gds(id=item.user_id or beatmapset.user_id, username=beatmapset.creator)]
        for item in difficulties
    ]
    avatar_ids = {beatmapset.user_id}
    avatar_ids.update(owner.id for owners in difficulty_owners for owner in owners)
    cover_task = asyncio.create_task(
        beatmap_background_data_uri(
            difficulties[0].id,
            beatmapset.id,
            f"https://assets.ppy.sh/beatmaps/{beatmapset.id}/covers/cover@2x.jpg",
        )
    )
    ordered_avatar_ids = sorted(avatar_ids)
    avatar_results = await asyncio.gather(*(_avatar_data_uri(user_id) for user_id in ordered_avatar_ids))
    avatars = dict(zip(ordered_avatar_ids, avatar_results))
    cover = await cover_task
    avatar = avatars[beatmapset.user_id]
    show_difficulty_owners = _has_different_owners(difficulty_owners)
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
        "show_difficulty_owners": show_difficulty_owners,
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
                "owners": [
                    {
                        "id": owner.id,
                        "username": owner.username,
                        "avatar": avatars[owner.id],
                    }
                    for owner in owners
                ],
            }
            for item, owners in zip(difficulties, difficulty_owners)
        ],
    }
    visible_count = min(len(difficulties), 20)
    viewport_height = 1000 + max(0, visible_count - 9) * 65
    return await render_map_template(TEMPLATE_PATH, payload, "bmap-refined", viewport_height)
