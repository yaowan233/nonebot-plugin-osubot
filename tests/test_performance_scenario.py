from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_parse_performance_scenario_supports_map_parameters():
    from nonebot_plugin_osubot.performance import parse_performance_scenario

    scenario = parse_performance_scenario(
        [("acc", "=", "98.5"), ("miss", "=", "1"), ("combo", "=", "800"), ("rate", "=", "1.2")]
    )

    assert scenario is not None
    assert scenario.accuracy == 98.5
    assert scenario.misses == 1
    assert scenario.combo == 800
    assert scenario.clock_rate == 1.2
    assert scenario.lazer is True


@pytest.mark.parametrize(
    ("conditions", "message"),
    [
        ([("acc", ">", "98")], "仅支持 ="),
        ([("acc", "=", "101")], "不超过 100"),
        ([("rate", "=", "2.1")], "0.5 到 2.0"),
        ([("foo", "=", "1")], "不支持情景参数"),
    ],
)
def test_parse_performance_scenario_rejects_invalid_values(conditions, message):
    from nonebot_plugin_osubot.performance import PerformanceScenarioError, parse_performance_scenario

    with pytest.raises(PerformanceScenarioError, match=message):
        parse_performance_scenario(conditions)


def test_calculate_performance_scenarios_uses_osu_tools_batch():
    from nonebot_plugin_osubot import performance

    requests = []

    def calculate_many(batch):
        requests.extend(batch)
        return [SimpleNamespace(pp=r["acc"] * 2, stars=5.5, max_combo=1200) for r in batch]

    calculator = SimpleNamespace(
        map_attributes=lambda *args: SimpleNamespace(n_objects=1000),
        calculate_many=calculate_many,
    )
    with patch.object(performance, "get_osu_calculator", return_value=calculator):
        points = performance.calculate_performance_scenarios(
            "map.osu",
            0,
            ["HD"],
            [
                performance.PerformanceScenario(accuracy=98, misses=1, combo=800, clock_rate=1.1),
                performance.PerformanceScenario(accuracy=100, misses=1, combo=800, clock_rate=1.1),
            ],
        )
    assert [p.pp for p in points] == [196, 200]
    assert all(p.stars == 5.5 and p.max_combo == 1200 for p in points)
    assert [r["acc"] for r in requests] == [98, 100]
    assert all(r["combo"] == 800 and r["misses"] == 1 for r in requests)
    assert requests[0]["mods"] == ["HD", {"acronym": "DT", "settings": {"speed_change": 1.1}}]
