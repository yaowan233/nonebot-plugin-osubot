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


def test_calculate_performance_scenarios_shares_difficulty():
    from nonebot_plugin_osubot import performance

    beatmap = SimpleNamespace(mode=performance.GAME_MODES[0], n_objects=1000, is_suspicious=lambda: False)
    difficulty = SimpleNamespace(stars=5.5, max_combo=1200)
    calculated = []

    class FakeDifficulty:
        def __init__(self, **kwargs):
            assert kwargs == {"mods": ["HD"], "clock_rate": 1.1}

        def calculate(self, value):
            assert value is beatmap
            return difficulty

    class FakePerformance:
        def __init__(self, **kwargs):
            calculated.append(kwargs)
            self.kwargs = kwargs

        def calculate(self, value):
            assert value is difficulty
            return SimpleNamespace(pp=self.kwargs["accuracy"] * 2)

    with (
        patch.object(performance, "Beatmap", return_value=beatmap),
        patch.object(performance, "Difficulty", FakeDifficulty),
        patch.object(performance, "Performance", FakePerformance),
    ):
        points = performance.calculate_performance_scenarios(
            "map.osu",
            0,
            ["HD"],
            [
                performance.PerformanceScenario(accuracy=98, misses=1, combo=800, clock_rate=1.1),
                performance.PerformanceScenario(accuracy=100, misses=1, combo=800, clock_rate=1.1),
            ],
        )

    assert [point.pp for point in points] == [196, 200]
    assert all(point.stars == 5.5 and point.max_combo == 1200 for point in points)
    assert [item["accuracy"] for item in calculated] == [98, 100]
