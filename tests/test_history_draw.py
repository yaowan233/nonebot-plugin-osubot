from io import BytesIO

import pytest
from PIL import Image


def test_build_history_data_calculates_summary():
    from nonebot_plugin_osubot.draw.echarts import build_history_data

    result = build_history_data(
        [1000, 1100, 1250],
        ["2026-01-01", "2026-02-01", "2026-02-15"],
        [10000, 9000, 8000],
        "player mania pp/rank history",
        username="player",
        mode="mania",
        user_id=123,
    )

    assert result["period_days"] == 45
    assert result["pp_gain"] == 250
    assert result["recent_pp_gain"] == 150
    assert result["rank_gain"] == 2000
    assert result["rank_gain_rate"] == 20
    assert result["mode"] == "键盘模式"
    assert result["avatar"] == "https://a.ppy.sh/123"


def test_build_history_data_supports_one_point():
    from nonebot_plugin_osubot.draw.echarts import build_history_data

    result = build_history_data([1000], ["2026-01-01"], [10000], "player osu history")

    assert result["period_days"] == 1
    assert result["pp_gain"] == 0
    assert result["recent_pp_gain"] == 0
    assert result["rank_gain"] == 0


def test_build_history_data_limits_registration_rank_surge():
    from nonebot_plugin_osubot.draw.echarts import build_history_data

    dates = [f"2026-{month:02d}-01" for month in range(1, 13)]
    ranks = [
        3_000_000,
        1_200_000,
        460_000,
        180_000,
        124_000,
        118_000,
        114_000,
        111_000,
        109_000,
        107_000,
        105_000,
        103_000,
    ]
    result = build_history_data(
        [1000 + index * 100 for index in range(len(dates))],
        dates,
        ranks,
        "new player osu history",
    )

    assert result["rank_window_limited"] is True
    assert result["rank_start_index"] > 0
    assert result["rank_display_values"][: result["rank_start_index"]] == [None] * result["rank_start_index"]
    visible_ranks = [rank for rank in result["rank_display_values"] if rank is not None]
    assert max(visible_ranks) - min(visible_ranks) < max(ranks) - min(ranks)
    assert result["pp_values"] == [1000 + index * 100 for index in range(len(dates))]
    assert result["rank_gain"] == visible_ranks[0] - visible_ranks[-1]


def test_build_history_data_keeps_normal_rank_history():
    from nonebot_plugin_osubot.draw.echarts import build_history_data

    ranks = [30_000, 28_000, 27_500, 26_000, 25_500, 24_000, 23_000, 22_500]
    result = build_history_data(
        [2000 + index * 50 for index in range(len(ranks))],
        [f"2026-01-{index + 1:02d}" for index in range(len(ranks))],
        ranks,
        "player osu history",
    )

    assert result["rank_window_limited"] is False
    assert result["rank_start_index"] == 0
    assert result["rank_display_values"] == ranks


@pytest.mark.asyncio
async def test_draw_history_plot_uses_native_renderer(monkeypatch):
    from nonebot_plugin_osubot.draw import echarts

    async def fail_if_browser_is_used(*_args, **_kwargs):
        raise AssertionError("history rendering must not use the browser template path")

    monkeypatch.setattr(echarts, "_render_chart_template", fail_if_browser_is_used)
    result = await echarts.draw_history_plot(
        [1000, 1100, 1200],
        ["2026-01-01", "2026-01-02", "2026-01-03"],
        [10_000, 9_500, 9_000],
        "player osu history",
        username="player",
        mode="osu",
    )

    assert isinstance(result, BytesIO)
    with Image.open(result) as image:
        assert image.format == "JPEG"
        assert image.size == (1280, 760)
