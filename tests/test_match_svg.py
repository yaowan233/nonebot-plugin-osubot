from io import BytesIO

from PIL import Image
import pytest


def _players(count: int, team: str = "none") -> list[dict]:
    return [
        {
            "user_id": index + 1,
            "name": f"Player {index + 1}",
            "avatar_data": None,
            "team": team,
            "passed": True,
            "score": 1_000_000 - index * 50_000,
            "accuracy": 99.5 - index * 0.4,
            "combo": 1200 - index * 50,
            "mods": ["HD"] if index % 2 == 0 else [],
        }
        for index in range(count)
    ]


def _game(index: int, *, team: bool, players_per_side: int = 4) -> dict:
    if team:
        red = _players(players_per_side, "red")
        blue = _players(players_per_side, "blue")
        players = sorted([*red, *blue], key=lambda player: player["score"], reverse=True)
    else:
        players = _players(players_per_side)
        red = []
        blue = []
    return {
        "index": index,
        "map_id": 1000 + index,
        "title": f"Tournament Map {index}",
        "version": "Insane",
        "creator": "mapper",
        "cover_data": None,
        "stars": 6.42,
        "winner": "red" if team else "none",
        "red_score": sum(player["score"] for player in red),
        "blue_score": sum(player["score"] for player in blue),
        "players": players,
        "red_players": red,
        "blue_players": blue,
    }


def _payload(*, team: bool, game_count: int, players_per_side: int) -> dict:
    return {
        "match_id": "123456",
        "title": "OSUBOT Summer Cup Finals" if team else "Weekend Lobby",
        "team_type": "team-vs" if team else "head-to-head",
        "is_team": team,
        "red_name": "Crimson Nova",
        "blue_name": "Azure Echo",
        "red_wins": game_count,
        "blue_wins": 0,
        "game_count": game_count,
        "player_count": players_per_side if not team else players_per_side * 2,
        "team_size": players_per_side,
        "duration": "1h 38m",
        "time_range": "2026/09/02 19:30—21:08",
        "complete": True,
        "page_index": 1,
        "page_count": 1,
        "games": [_game(index + 1, team=team, players_per_side=players_per_side) for index in range(game_count)],
    }


def test_match_svg_team_layout_and_dynamic_height():
    from nonebot_plugin_osubot.draw.match_svg import build_match_svg

    svg, width, height = build_match_svg(_payload(team=True, game_count=3, players_per_side=4))

    assert width == 1280
    assert height == 196 + 22 + 3 * (92 + 34 + 4 * 52) + 2 * 20 + 16 + 60
    assert svg.count('data-role="match-game"') == 3
    assert "Crimson Nova" in svg
    assert "Azure Echo" in svg
    assert "MULTIPLAYER · FULL SCOREBOARD" in svg


def test_match_svg_h2h_layout_and_dynamic_height():
    from nonebot_plugin_osubot.draw.match_svg import build_match_svg

    svg, width, height = build_match_svg(_payload(team=False, game_count=2, players_per_side=5))

    assert width == 900
    assert height == 160 + 20 + 2 * (94 + 38 + 5 * 62) + 20 + 16 + 60
    assert svg.count('data-role="match-game"') == 2
    assert "HEAD-TO-HEAD · FULL SCOREBOARD" in svg
    assert "Player 5" in svg


@pytest.mark.asyncio
@pytest.mark.parametrize("team", [True, False])
async def test_match_svg_raster_smoke(team: bool):
    from nonebot_plugin_osubot.draw.match_svg import render_match_svg

    payload = _payload(team=team, game_count=1, players_per_side=2)
    result = await render_match_svg(payload)

    with Image.open(BytesIO(result)) as image:
        assert image.width == (1280 if team else 900)
        assert image.height == 900
