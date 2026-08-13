from io import BytesIO
import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _score() -> SimpleNamespace:
    return SimpleNamespace(ended_at=datetime.now(), mods=[])


@pytest.mark.asyncio
async def test_plain_bp_range_only_requests_needed_api_rows():
    import nonebot_plugin_osubot.draw.bp as bp

    scores = [_score() for _ in range(20)]
    get_scores = AsyncMock(return_value=scores)
    with (
        patch.object(bp, "get_user_scores", new=get_scores),
        patch.object(bp, "cal_score_info", side_effect=lambda _is_lazer, score, _source: score),
    ):
        _all_scores, selected = await bp.select_bp_scores("bp", 1, True, "osu", [], 1, 20, 0, [], "osu")

    assert selected == scores
    assert get_scores.await_args.kwargs["limit"] == 20


@pytest.mark.asyncio
async def test_filtered_bp_still_requests_full_search_window():
    import nonebot_plugin_osubot.draw.bp as bp

    scores = [_score()]
    get_scores = AsyncMock(return_value=scores)
    with (
        patch.object(bp, "get_user_scores", new=get_scores),
        patch.object(bp, "cal_score_info", side_effect=lambda _is_lazer, score, _source: score),
        patch.object(bp, "filter_scores_with_regex", return_value=scores),
    ):
        await bp.select_bp_scores("bp", 1, True, "osu", [], 1, 20, 0, [("title", "~", "map")], "osu")

    assert get_scores.await_args.kwargs["limit"] == 200


@pytest.mark.asyncio
async def test_draw_bp_fetches_user_and_scores_concurrently():
    import nonebot_plugin_osubot.draw.bp as bp

    info_started = asyncio.Event()
    info = object()

    async def get_info(*_args):
        info_started.set()
        return info

    async def select(*_args):
        await asyncio.wait_for(info_started.wait(), timeout=1)
        score = _score()
        return [score], [score]

    with (
        patch.object(bp, "get_user_info_data", side_effect=get_info),
        patch.object(bp, "select_bp_scores", side_effect=select),
        patch.object(bp, "draw_pfm", new=AsyncMock(return_value=BytesIO(b"image"))) as draw,
    ):
        result = await bp.draw_bp("bp", 1, True, "osu", [], 1, 20, 0, [], "osu")

    assert result.getvalue() == b"image"
    assert draw.await_args.kwargs["info"] is info


@pytest.mark.asyncio
async def test_bp_list_keeps_official_api_pp_while_calculating_modded_stars(tmp_path):
    import nonebot_plugin_osubot.draw.bp as bp

    beatmap = SimpleNamespace(
        id=456,
        set_id=123,
        checksum=None,
        stars=5.0,
        title="Map",
        artist="Artist",
        version="Insane",
    )
    score = SimpleNamespace(
        beatmap=beatmap,
        beatmapset=None,
        pp=321.45,
        accuracy=99.0,
        mods=[SimpleNamespace(acronym="DT", settings=None)],
        ended_at=SimpleNamespace(strftime=lambda _format: "2026.01.01"),
        score_version="lazer",
    )
    statistics = SimpleNamespace(model_dump=lambda: {"global_rank": 1, "pp": 1000})
    info = SimpleNamespace(
        id=1,
        username="player",
        country_code="CN",
        support_level=0,
        team=None,
        statistics=statistics,
    )
    osu_file = tmp_path / "123" / "456.osu"
    osu_file.parent.mkdir()
    osu_file.write_text("osu file", encoding="utf-8")

    with (
        patch.object(bp, "map_path", tmp_path),
        patch.object(bp, "get_user_info_data", new=AsyncMock(return_value=info)),
        patch.object(bp, "get_pfm_img", new=AsyncMock()),
        patch.object(bp, "ensure_osu_file", new=AsyncMock()),
        patch.object(bp, "_player_avatar_data_uri", new=AsyncMock(return_value=None)),
        patch.object(bp, "_team_icon_data", new=AsyncMock(return_value=None)),
        patch.object(bp, "cal_stars", return_value=8.76),
        patch.object(bp, "render_bp_svg", new=AsyncMock(return_value=BytesIO(b"image"))) as render,
    ):
        result = await bp.draw_pfm("bp", 1, [score], [score], "osu", "osu", 1, 1, 0)

    play = render.await_args.args[0]["plays"][0]
    assert result.getvalue() == b"image"
    assert play["pp"] == 321.45
    assert play["stars"] == 8.76
