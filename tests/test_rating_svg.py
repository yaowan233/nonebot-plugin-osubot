from io import BytesIO

import pytest
from PIL import Image


def _players(count: int) -> list[dict]:
    players = []
    for index in range(count):
        wins = max(1, 8 - index)
        losses = 2 + index
        played = wins + losses
        players.append(
            {
                "user_id": index + 1,
                "name": f"player-{index + 1}",
                "avatar_data": None,
                "team": "red" if index % 2 == 0 else "blue",
                "rating": 2.5 - index * 0.1,
                "total_score": 8_000_000 - index * 250_000,
                "average_score": 700_000 - index * 10_000,
                "wins": wins,
                "losses": losses,
                "played": played,
                "win_rate": wins / played,
                "record_text": f"{wins}W—{losses}L · {wins / played:.1%}",
                "top1_count": max(0, 5 - index),
                "top1_rate": max(0, 5 - index) / played,
            }
        )
    return players


def _data(team_type: str, count: int = 8) -> dict:
    players = _players(count)
    return {
        "match_id": "12345",
        "title": "OSUBOT Summer Cup Finals",
        "time_range": "2026/09/02 19:30—21:08",
        "team_type": team_type,
        "algorithm": "OSUPLUS",
        "game_count": 12,
        "player_count": len(players),
        "players": players,
        "mvp": players[0],
        "max_top1_count": max(player["top1_count"] for player in players),
        "max_total_score": max(player["total_score"] for player in players),
        "average_rating": sum(player["rating"] for player in players) / len(players),
        "red_name": "Crimson Nova",
        "blue_name": "Azure Echo",
        "red_wins": 7,
        "blue_wins": 5,
        "red_players": [player for player in players if player["team"] == "red"],
        "blue_players": [player for player in players if player["team"] == "blue"],
        "team_size": count // 2,
    }


@pytest.mark.parametrize(
    ("team_type", "count", "expected_height"),
    [("team-vs", 8, 900), ("team-vs", 16, 1061), ("head-to-head", 8, 1011)],
)
def test_rating_svg_uses_dynamic_layout_height(team_type: str, count: int, expected_height: int):
    from nonebot_plugin_osubot.draw.rating_svg import build_rating_svg

    svg, height = build_rating_svg(_data(team_type, count))

    assert height == expected_height
    assert f'height="{expected_height}"' in svg
    assert "OSUBOT Summer Cup Finals" in svg
    assert "player-1" in svg


@pytest.mark.asyncio
@pytest.mark.parametrize("team_type", ["team-vs", "head-to-head"])
async def test_rating_svg_renders_without_browser(team_type: str):
    from nonebot_plugin_osubot.draw.rating_svg import render_rating_svg

    result = await render_rating_svg(_data(team_type))

    assert isinstance(result, BytesIO)
    with Image.open(result) as image:
        assert image.size == (1280, 900 if team_type == "team-vs" else 1011)


@pytest.mark.asyncio
async def test_draw_rating_card_delegates_to_native_renderer(monkeypatch):
    from nonebot_plugin_osubot.draw import rating

    prepared = _data("team-vs")

    async def fake_prepare(data):
        assert data is prepared
        return data

    async def fake_render(data):
        assert data is prepared
        return BytesIO(b"native-rating")

    monkeypatch.setattr(rating, "_prepare_rating_data", fake_prepare, raising=False)
    monkeypatch.setattr(rating, "render_rating_svg", fake_render, raising=False)

    assert await rating.draw_rating_card(prepared) == b"native-rating"
