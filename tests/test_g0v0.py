from unittest.mock import AsyncMock

import pytest


def _g0v0_score_payload() -> dict:
    return {
        "accuracy": 0.9876,
        "beatmap_id": 2553242,
        "best_id": 1,
        "build_id": None,
        "ended_at": "2026-08-28T12:00:00Z",
        "has_replay": False,
        "id": 123,
        "is_perfect_combo": False,
        "legacy_perfect": False,
        "max_combo": 500,
        "maximum_statistics": {"great": 1000, "miss": 1},
        "mods": [{"acronym": "RX"}],
        "passed": True,
        "pp": 321.45,
        "preserve": True,
        "rank": "A",
        "ranked": True,
        "ruleset_id": 0,
        "started_at": "2026-08-28T11:57:00Z",
        "statistics": {"great": 1000, "miss": 1},
        "total_score": 1_000_000,
        "type": "solo_score",
        "user_id": 408,
    }


def _official_map_payload() -> dict:
    return {
        "id": 2553242,
        "beatmapset_id": 123456,
        "version": "Insane",
        "total_length": 180,
        "mode": "osu",
        "mode_int": 0,
        "bpm": 200,
        "cs": 4,
        "accuracy": 8,
        "ar": 9,
        "drain": 6,
        "difficulty_rating": 5.67,
        "checksum": "0123456789abcdef0123456789abcdef",
        "user_id": 42,
        "convert": False,
        "status": "ranked",
        "is_scoreable": True,
        "max_combo": 600,
        "count_circles": 500,
        "count_sliders": 400,
        "count_spinners": 2,
        "beatmapset": {"id": 123456, "artist": "artist", "title": "title", "creator": "mapper"},
    }


@pytest.mark.asyncio
async def test_g0v0_map_scores_uses_ruleset_and_fallback_map(monkeypatch):
    from nonebot_plugin_osubot import api

    request = AsyncMock(return_value=[_g0v0_score_payload()])
    monkeypatch.setattr(api, "g0v0_make_request", request)

    scores = await api.g0v0_map_scores(2553242, 408, "rxosu", _official_map_payload())

    called_url = request.await_args.args[0]
    assert "ruleset=osurx" in called_url
    assert "mode=" not in called_url
    assert len(scores) == 1
    assert scores[0].beatmap.set_id == 123456
    assert scores[0].beatmap.artist == "artist"
    assert scores[0].beatmap.title == "title"
    assert scores[0].beatmap.stars == 5.67


@pytest.mark.asyncio
async def test_g0v0_headers_stay_anonymous_after_token_failure(monkeypatch):
    from nonebot_plugin_osubot import api

    api.g0v0_token_cache.clear()
    monkeypatch.setattr(api, "_g0v0_token_failed", True)

    assert await api.g0v0_headers() == {"x-api-version": "20220705"}
