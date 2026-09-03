from io import BytesIO

import pytest
from PIL import Image


def make_players(count: int) -> list[dict]:
    return [
        {
            "osu_id": index,
            "osu_name": f"player-{index}",
            "qq_name": f"qq-{index}",
            "avatar_url": "",
            "pp": 20_000 - index,
            "global_rank": index,
            "delta": float(index),
        }
        for index in range(1, count + 1)
    ]


def test_rank_display_pins_requester_below_top_20():
    from nonebot_plugin_osubot.draw.rank import prepare_rank_display

    data = prepare_rank_display(make_players(100), requester_osu_id=76)

    assert data["total_count"] == 100
    assert [player["place"] for player in data["podium"]] == [2, 1, 3]
    assert len(data["visible"]) == 20
    assert data["pinned"]["place"] == 76
    assert data["hidden_end"] == 75


def test_rank_display_does_not_duplicate_visible_requester():
    from nonebot_plugin_osubot.draw.rank import prepare_rank_display

    data = prepare_rank_display(make_players(30), requester_osu_id=6)

    assert data["pinned"] is None
    assert sum(player["is_self"] for player in data["visible"]) == 1


def test_rank_display_excludes_players_below_threshold():
    from nonebot_plugin_osubot.draw.rank import prepare_rank_display

    players = make_players(3)
    players[-1]["pp"] = 99

    data = prepare_rank_display(players, requester_osu_id=3)

    assert data["total_count"] == 2
    assert data["pinned"] is None


def _rank_payload(count: int, requester_osu_id: int | None = None) -> dict:
    from nonebot_plugin_osubot.draw.rank import prepare_rank_display

    data = prepare_rank_display(make_players(count), requester_osu_id)
    for player in data["visible"]:
        player["avatar_data"] = None
    if data["pinned"]:
        data["pinned"]["avatar_data"] = None
    return {**data, "mode_name": "标准模式", "updated_at": "2026/09/02 16:40"}


@pytest.mark.parametrize(
    ("count", "requester_osu_id", "expected_height"),
    [(3, 2, 504), (20, 6, 1319), (100, 76, 1398)],
)
def test_rank_svg_preserves_dynamic_layout(count: int, requester_osu_id: int, expected_height: int):
    from nonebot_plugin_osubot.draw.rank_svg import build_rank_svg

    svg, height = build_rank_svg(_rank_payload(count, requester_osu_id))

    assert height == expected_height
    assert f'height="{expected_height}"' in svg
    assert svg.count('data-role="rank-podium"') == min(3, count)
    assert "群内 PP 排名 · 标准模式" in svg
    if count == 100:
        assert 'data-role="pinned-row"' in svg
        assert "已省略第 21—75 名" in svg


@pytest.mark.asyncio
async def test_rank_svg_raster_smoke():
    from nonebot_plugin_osubot.draw.rank_svg import render_rank_svg

    result = await render_rank_svg(_rank_payload(100, 76))

    assert isinstance(result, BytesIO)
    with Image.open(result) as image:
        assert image.size == (1280, 1398)


@pytest.mark.asyncio
async def test_rank_svg_raster_ignores_xml_invalid_player_characters():
    from nonebot_plugin_osubot.draw.rank_svg import render_rank_svg

    payload = _rank_payload(3, 2)
    payload["visible"][0]["osu_name"] = "player\x0bname"

    result = await render_rank_svg(payload)

    assert isinstance(result, BytesIO)


@pytest.mark.asyncio
async def test_draw_group_rank_delegates_to_native_renderer(monkeypatch):
    from nonebot_plugin_osubot.draw import rank

    async def fake_prepare(data):
        return data

    async def fake_render(data):
        assert data["mode_name"] == "标准模式"
        return BytesIO(b"native-rank")

    monkeypatch.setattr(rank, "_prepare_rank_avatars", fake_prepare, raising=False)
    monkeypatch.setattr(rank, "render_rank_svg", fake_render, raising=False)

    result = await rank.draw_group_rank(make_players(3), 2, "标准模式", "2026/09/02 16:40")

    assert result == b"native-rank"
