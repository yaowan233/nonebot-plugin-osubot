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
async def test_first_place_scores_use_official_firsts_scope():
    import nonebot_plugin_osubot.draw.bp as bp

    scores = [_score() for _ in range(20)]
    get_scores = AsyncMock(return_value=scores)
    with (
        patch.object(bp, "get_user_scores", new=get_scores),
        patch.object(bp, "cal_score_info", side_effect=lambda _is_lazer, score, _source: score),
    ):
        _all_scores, selected = await bp.select_bp_scores("firsts", 1, True, "osu", [], 1, 20, 0, [], "osu")

    assert selected == scores
    assert get_scores.await_args.args[2] == "firsts"
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


@pytest.mark.asyncio
async def test_draw_pfm_rejects_an_empty_score_list():
    import nonebot_plugin_osubot.draw.bp as bp
    from nonebot_plugin_osubot.exceptions import NetworkError

    with pytest.raises(NetworkError, match="未查询到游玩记录"):
        await bp.draw_pfm("prlist", 1, [], [], "osu", "osu")


def test_bp_list_only_requires_osu_files_for_local_calculation():
    from nonebot_plugin_osubot.draw.bp import _requires_osu_file

    def score(pp, acronym):
        return SimpleNamespace(pp=pp, mods=[SimpleNamespace(acronym=acronym)])

    assert not _requires_osu_file(score(321.45, "HD"))
    assert not _requires_osu_file(score(321.45, "CL"))
    assert _requires_osu_file(score(321.45, "DT"))
    assert _requires_osu_file(score(321.45, "DA"))
    assert _requires_osu_file(score(None, "HD"))


def test_bp_list_caches_locally_calculated_pp(tmp_path):
    import nonebot_plugin_osubot.draw.bp as bp

    osu_file = tmp_path / "map.osu"
    osu_file.write_text("osu file", encoding="utf-8")
    score = SimpleNamespace(
        ruleset_id=0,
        mods=[],
        accuracy=99.0,
        max_combo=100,
        legacy_total_score=1_000_000,
        statistics=SimpleNamespace(model_dump=lambda **_: {"great": 100}),
    )
    bp._calculated_pp_cache.clear()
    with patch.object(bp, "cal_pp", return_value=SimpleNamespace(pp=456.78)) as cal_pp:
        assert bp._calculated_pp(score, osu_file, "osu") == 456.78
        assert bp._calculated_pp(score, osu_file, "osu") == 456.78

    cal_pp.assert_called_once()
    bp._calculated_pp_cache.clear()


@pytest.mark.asyncio
async def test_first_place_list_uses_distinct_heading(tmp_path):
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
        pp=None,
        accuracy=99.0,
        mods=[],
        ended_at=SimpleNamespace(strftime=lambda _format: "2026.01.01"),
        score_version="lazer",
    )
    statistics = SimpleNamespace(model_dump=lambda: {"global_rank": 1})
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
        patch.object(bp, "get_pfm_img", new=AsyncMock()),
        patch.object(bp, "ensure_osu_file", new=AsyncMock()),
        patch.object(bp, "_player_avatar_data_uri", new=AsyncMock(return_value=None)),
        patch.object(bp, "_team_icon_data", new=AsyncMock(return_value=None)),
        patch.object(bp, "cal_stars", return_value=5.0),
        patch.object(bp, "cal_pp", return_value=SimpleNamespace(pp=456.78)) as cal_pp,
        patch.object(bp, "render_bp_svg", new=AsyncMock(return_value=BytesIO(b"image"))) as render,
    ):
        result = await bp.draw_pfm("firsts", 1, [score], [score], "osu", "osu", 1, 1, info=info)

    payload = render.await_args.args[0]
    assert result.getvalue() == b"image"
    assert payload["section_title"] == "第一名成绩"
    assert payload["range_label"] == "榜一 1–1"
    assert payload["plays"][0]["pp"] == 456.78
    cal_pp.assert_called_once()
