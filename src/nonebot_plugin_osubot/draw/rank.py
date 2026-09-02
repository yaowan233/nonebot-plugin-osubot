import re
import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from PIL import Image

from .score import _image_data_uri, _owner_avatar_data
from .rank_svg import render_rank_svg


def prepare_rank_display(players: list[dict[str, Any]], requester_osu_id: int | None) -> dict[str, Any]:
    """Select the top 20 and pin the requester when they rank below the fold."""
    ranked = sorted(
        (player for player in players if player["pp"] >= 100),
        key=lambda player: player["pp"],
        reverse=True,
    )
    for place, player in enumerate(ranked, start=1):
        player["place"] = place
        player["is_self"] = player["osu_id"] == requester_osu_id

    visible = ranked[:20]
    requester = next((player for player in ranked if player["is_self"]), None)
    pinned = requester if requester and requester["place"] > 20 else None
    return {
        "total_count": len(ranked),
        "podium": [ranked[index] for index in (1, 0, 2) if index < len(ranked)],
        "visible": visible,
        "rows": visible[3:],
        "pinned": pinned,
        "hidden_start": 21,
        "hidden_end": pinned["place"] - 1 if pinned else None,
    }


async def draw_group_rank(
    players: list[dict[str, Any]],
    requester_osu_id: int | None,
    mode_name: str,
    updated_at: str,
) -> bytes:
    data = prepare_rank_display(players, requester_osu_id)
    data.update({"mode_name": mode_name, "updated_at": updated_at})
    data = await _prepare_rank_avatars(data)
    return (await render_rank_svg(data)).getvalue()


def _local_rank_avatar_data_uri(path: Path) -> str:
    with Image.open(path) as avatar:
        return _image_data_uri(avatar, max_size=(128, 128))


async def _rank_avatar_data_uri(player: dict) -> str | None:
    source = str(player.get("avatar_data") or player.get("avatar_url") or "")
    if source.startswith("data:"):
        return source
    try:
        if source.startswith("file:"):
            raw_path = unquote(urlparse(source).path)
            if re.match(r"^/[A-Za-z]:/", raw_path):
                raw_path = raw_path[1:]
            local_path = Path(raw_path)
            if local_path.is_file():
                return await asyncio.to_thread(_local_rank_avatar_data_uri, local_path)
        elif source and Path(source).is_file():
            return await asyncio.to_thread(_local_rank_avatar_data_uri, Path(source))
    except (OSError, ValueError):
        pass
    try:
        return await _owner_avatar_data(int(player["osu_id"]))
    except (KeyError, TypeError, ValueError):
        return None


async def _prepare_rank_avatars(data: dict[str, Any]) -> dict[str, Any]:
    displayed = list(data.get("visible") or [])
    if data.get("pinned"):
        displayed.append(data["pinned"])
    avatars = await asyncio.gather(*(_rank_avatar_data_uri(player) for player in displayed))
    for player, avatar in zip(displayed, avatars):
        player["avatar_data"] = avatar
    return data
