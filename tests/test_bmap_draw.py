from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def test_same_owner_on_every_difficulty_does_not_show_repeated_avatars():
    from nonebot_plugin_osubot.draw.bmap import _has_different_owners
    from nonebot_plugin_osubot.schema.beatmap import Gds

    owner = Gds(id=10, username="Mapper")

    assert _has_different_owners([[owner], [owner], [owner]]) is False


@pytest.mark.asyncio
async def test_bmap_payload_includes_per_difficulty_owner_avatars():
    from nonebot_plugin_osubot.draw.bmap import draw_bmap_info

    first = SimpleNamespace(
        id=101,
        version="Mapper A's Hard",
        mode_int=0,
        difficulty_rating=4.2,
        total_length=120,
        max_combo=500,
        cs=4,
        ar=9,
        accuracy=8,
        drain=6,
        playcount=1000,
        passcount=250,
        user_id=11,
        owners=[SimpleNamespace(id=11, username="Mapper A")],
    )
    second = SimpleNamespace(
        id=102,
        version="Collab Extra",
        mode_int=0,
        difficulty_rating=6.3,
        total_length=125,
        max_combo=600,
        cs=4,
        ar=9.5,
        accuracy=9,
        drain=6,
        playcount=800,
        passcount=100,
        user_id=22,
        owners=[SimpleNamespace(id=22, username="Mapper B"), SimpleNamespace(id=33, username="Mapper C")],
    )
    beatmapset = SimpleNamespace(
        id=1,
        title="Test Map",
        artist="Artist",
        creator="Set Owner",
        user_id=10,
        source="",
        bpm=180,
        ranked=1,
        ranked_date="2026-01-01T00:00:00Z",
        favourite_count=50,
        tags="test",
        beatmaps=[first, second],
    )

    async def avatar(url: str) -> str:
        return f"data:{url}"

    with (
        patch("nonebot_plugin_osubot.draw.bmap.get_beatmapsets_info", new=AsyncMock(return_value=beatmapset)),
        patch("nonebot_plugin_osubot.draw.bmap.beatmap_background_data_uri", new=AsyncMock(return_value="cover")),
        patch("nonebot_plugin_osubot.draw.bmap.remote_image_data_uri", new=AsyncMock(side_effect=avatar)),
        patch(
            "nonebot_plugin_osubot.draw.bmap.render_map_template", new=AsyncMock(return_value=BytesIO(b"image"))
        ) as render,
    ):
        result = await draw_bmap_info(1)

    payload = render.await_args.args[1]
    assert result.getvalue() == b"image"
    assert payload["show_difficulty_owners"] is True
    assert [owner["username"] for owner in payload["difficulties"][0]["owners"]] == ["Mapper A"]
    assert [owner["username"] for owner in payload["difficulties"][1]["owners"]] == ["Mapper B", "Mapper C"]
    assert payload["difficulties"][1]["owners"][1]["avatar"].endswith("/33")
