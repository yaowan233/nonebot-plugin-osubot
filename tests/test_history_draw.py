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
