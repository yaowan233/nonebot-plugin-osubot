from unittest.mock import AsyncMock

import pytest


def _user(user_id: int, name: str) -> dict:
    return {
        "id": user_id,
        "username": name,
        "avatar_url": f"https://example.com/{user_id}.png",
        "country_code": "CN",
        "default_group": "default",
        "is_active": True,
        "is_bot": False,
        "is_deleted": False,
        "is_online": False,
        "is_supporter": False,
    }


def _beatmap() -> dict:
    cover = "https://example.com/cover.jpg"
    return {
        "id": 11,
        "beatmapset_id": 22,
        "difficulty_rating": 5.0,
        "mode": "osu",
        "status": "ranked",
        "total_length": 120,
        "user_id": 1,
        "version": "Insane",
        "beatmapset": {
            "id": 22,
            "artist": "Artist",
            "artist_unicode": "Artist",
            "covers": {"cover": cover, "card": cover, "list": cover, "slimcover": cover},
            "creator": "Mapper",
            "favourite_count": 0,
            "nsfw": False,
            "play_count": 0,
            "preview_url": "",
            "source": "",
            "status": "ranked",
            "title": "Song",
            "title_unicode": "Song",
            "user_id": 1,
            "video": False,
        },
    }


def _score(user_id: int, score: int, team: str, *, passed: bool) -> dict:
    return {
        "user_id": user_id,
        "accuracy": 0.98,
        "mods": [],
        "score": score,
        "max_combo": 100,
        "perfect": 0,
        "statistics": {},
        "passed": passed,
        "rank": "A" if passed else "F",
        "created_at": "2026-08-24T00:00:00Z",
        "mode": "osu",
        "mode_int": 0,
        "match": {"team": team, "passed": passed},
    }


def _traditional_match() -> dict:
    return {
        "match": {
            "id": 1,
            "name": "Lobby",
            "start_time": "2026-08-24T00:00:00+00:00",
            "end_time": "2026-08-24T01:00:00+00:00",
        },
        "events": [
            {
                "id": 1,
                "detail": {"type": "other"},
                "timestamp": "2026-08-24T01:00:00Z",
                "game": {
                    "beatmap_id": 11,
                    "mods": [],
                    "beatmap": _beatmap(),
                    "team_type": "team-vs",
                    "scores": [
                        _score(1, 100, "red", passed=False),
                        _score(2, 0, "red", passed=False),
                        _score(3, 90, "blue", passed=True),
                    ],
                },
            }
        ],
        "users": [_user(1, "red"), _user(2, "zero"), _user(3, "blue")],
    }


def test_traditional_match_preserves_score_filter_and_winner(after_nonebot_init):
    from nonebot_plugin_osubot.draw.match_history import prepare_match_data
    from nonebot_plugin_osubot.schema.match import Match

    data = prepare_match_data(Match(**_traditional_match()), "1", team_type_filter="team-vs")

    assert [player["name"] for player in data["games"][0]["players"]] == ["red", "blue"]
    assert data["games"][0]["red_score"] == 100
    assert data["games"][0]["winner"] == "red"


@pytest.mark.asyncio
async def test_lazer_room_conversion_satisfies_match_schema(after_nonebot_init, monkeypatch):
    from nonebot_plugin_osubot import match_room
    from nonebot_plugin_osubot.schema.match import Match

    metadata = match_room.RoomEventMetadata(
        teams_by_playlist={7: {"1": "red"}},
        room_types_by_playlist={7: "team_versus"},
    )
    monkeypatch.setattr(match_room, "fetch_room_event_metadata", AsyncMock(return_value=metadata))
    monkeypatch.setattr(
        match_room,
        "api_info",
        AsyncMock(
            return_value={
                "scores": [
                    {
                        "user_id": 1,
                        "total_score": 123,
                        "accuracy": 0.99,
                        "max_combo": 50,
                        "mods": [{"acronym": "HD"}],
                        "statistics": {"great": 10, "miss": 1},
                        "passed": True,
                        "rank": "A",
                        "ended_at": "2026-08-24T01:00:00Z",
                        "user": _user(1, "player"),
                    }
                ]
            }
        ),
    )
    raw = {
        "id": 9,
        "name": "Lazer room",
        "type": "head_to_head",
        "starts_at": "2026-08-24T00:00:00+00:00",
        "ends_at": "2026-08-24T01:00:00+00:00",
        "host": _user(1, "player"),
        "playlist": [
            {
                "id": 7,
                "played_at": "2026-08-24T01:00:00Z",
                "beatmap_id": 11,
                "required_mods": [{"acronym": "HR"}],
                "beatmap": _beatmap(),
            }
        ],
    }

    converted = await match_room.convert_room_to_match(raw, "9")
    match = Match(**converted)

    score = match.events[0].game.scores[0]
    assert score.mods == ["HD"]
    assert score.statistics.count_300 == 10
    assert score.match == {"team": "red", "passed": True}


@pytest.mark.asyncio
async def test_draw_match_history_keeps_return_data_contract(after_nonebot_init, monkeypatch):
    from nonebot_plugin_osubot.draw import match_history

    monkeypatch.setattr(match_history, "api_info", AsyncMock(return_value=_traditional_match()))
    monkeypatch.setattr(match_history, "draw_match_card", AsyncMock(return_value=b"image"))
    monkeypatch.setattr(match_history, "compress_jpeg", lambda image: image)

    image, data = await match_history.draw_match_history("1", query_type="match", return_data=True)

    assert image == b"image"
    assert data["match_id"] == "1"
    assert data["games"][0]["winner"] == "red"
