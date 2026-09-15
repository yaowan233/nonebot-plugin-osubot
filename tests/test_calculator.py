from pathlib import Path

import pytest


FIXTURE = Path(__file__).parent / "fixtures" / "calculator-mania.osu"


def test_mania_matrix_uses_official_generated_statistics():
    from nonebot_plugin_osubot.pp import get_osu_calculator
    from nonebot_plugin_osubot.draw.map import _performance_payload

    calculator = get_osu_calculator()
    result = calculator.calculate(str(FIXTURE), 3, [], 90)
    assert result.is_success
    assert sum(result.stats_used.values()) == 200
    assert result.stats_used["Good"] == 200
    matrix, components = _performance_payload(FIXTURE, 3, [])
    assert [point["accuracy"] for point in matrix["pp_matrix"]] == [100, 99, 98, 95, 90]
    assert matrix["pp_matrix"][-1]["pp"] == result.pp
    assert components["difficulty"] >= 0


def test_mania_metadata_and_explicit_statistics():
    from nonebot_plugin_osubot.pp import get_osu_calculator

    calculator = get_osu_calculator()
    metadata = calculator.map_attributes(FIXTURE, 3)
    assert (metadata.mode, metadata.n_objects, metadata.n_circles, metadata.n_holds) == (3, 200, 200, 0)
    result = calculator.calculate(str(FIXTURE), 3, [], 99, statistics={"perfect": 180, "great": 20})
    assert result.stats_used["Perfect"] == 180
    assert result.stats_used["Great"] == 20


def test_mod_settings_have_distinct_cache_entries():
    from nonebot_plugin_osubot.pp import get_osu_calculator

    calculator = get_osu_calculator()
    slow = [{"acronym": "DT", "settings": {"speed_change": 1.2}}]
    fast = [{"acronym": "DT", "settings": {"speed_change": 1.5}}]
    assert calculator.calculate(str(FIXTURE), 3, fast).stars > calculator.calculate(str(FIXTURE), 3, slow).stars


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_ruleset_conversion_and_components(mode, tmp_path):
    from nonebot_plugin_osubot.pp import get_osu_calculator

    path = tmp_path / "standard.osu"
    path.write_text(FIXTURE.read_text(encoding="utf-8").replace("Mode: 3", "Mode: 0"), encoding="utf-8")
    calculator = get_osu_calculator()
    metadata = calculator.map_attributes(path, mode)
    result = calculator.calculate(str(path), mode, [], 99)
    assert metadata.mode == mode
    assert metadata.n_objects > 0
    assert result.is_success
    assert result.stars > 0
    assert result.pp_difficulty >= 0


def test_explicit_scenario_uses_osu_tools_settings():
    from nonebot_plugin_osubot.performance import calculate_performance_report, PerformanceScenario

    result = calculate_performance_report(FIXTURE, 3, [], PerformanceScenario(accuracy=97, clock_rate=1.2))
    assert result.requested.accuracy == 97
    assert result.requested.max_combo == 200
    assert len(result.points) == 7
