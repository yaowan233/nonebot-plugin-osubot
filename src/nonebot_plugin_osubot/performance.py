from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from rosu_pp_py import Beatmap, Difficulty, GameMode, Performance

from .schema.score import Mod


GAME_MODES = (GameMode.Osu, GameMode.Taiko, GameMode.Catch, GameMode.Mania)
SCENARIO_ACCURACIES = (92.0, 94.0, 96.0, 98.0, 99.0, 100.0)


class PerformanceScenarioError(ValueError):
    """Raised when a requested PP scenario cannot describe a valid play."""


@dataclass(frozen=True, slots=True)
class PerformanceScenario:
    accuracy: float = 100.0
    misses: int = 0
    combo: int | None = None
    clock_rate: float | None = None
    lazer: bool = True

    def with_accuracy(self, accuracy: float) -> PerformanceScenario:
        return replace(self, accuracy=accuracy)


@dataclass(frozen=True, slots=True)
class PerformancePoint:
    accuracy: float
    pp: float
    stars: float
    max_combo: int


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    scenario: PerformanceScenario
    requested: PerformancePoint
    points: tuple[PerformancePoint, ...]


_FIELD_ALIASES = {
    "acc": "accuracy",
    "accuracy": "accuracy",
    "a": "accuracy",
    "miss": "misses",
    "misses": "misses",
    "m": "misses",
    "combo": "combo",
    "cb": "combo",
    "c": "combo",
    "rate": "clock_rate",
    "clockrate": "clock_rate",
    "clock_rate": "clock_rate",
    "speed": "clock_rate",
    "lazer": "lazer",
    "legacy": "legacy",
}


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "是", "开"}:
        return True
    if normalized in {"0", "false", "no", "off", "否", "关"}:
        return False
    raise PerformanceScenarioError(f"无法识别布尔值：{value}")


def parse_performance_scenario(conditions: Sequence[tuple[str, str, str]]) -> PerformanceScenario | None:
    """Parse map-command filters into one explicit performance scenario."""
    if not conditions:
        return None

    values: dict[str, float | int | bool | None] = {}
    for raw_field, operator, raw_value in conditions:
        field = _FIELD_ALIASES.get(raw_field.strip().lower())
        if field is None:
            raise PerformanceScenarioError(f"不支持情景参数 {raw_field}，可用 acc、miss、combo、rate、lazer")
        if operator != "=":
            raise PerformanceScenarioError(f"情景参数 {raw_field} 仅支持 =")
        try:
            if field == "accuracy":
                values[field] = float(raw_value)
            elif field in {"misses", "combo"}:
                numeric = float(raw_value)
                if not numeric.is_integer():
                    raise ValueError
                values[field] = int(numeric)
            elif field == "clock_rate":
                values[field] = float(raw_value)
            elif field == "legacy":
                values["lazer"] = not _parse_bool(raw_value)
            else:
                values[field] = _parse_bool(raw_value)
        except ValueError as error:
            if isinstance(error, PerformanceScenarioError):
                raise
            raise PerformanceScenarioError(f"情景参数 {raw_field} 的值无效：{raw_value}") from error

    scenario = PerformanceScenario(**values)
    _validate_scenario_values(scenario)
    return scenario


def _validate_scenario_values(scenario: PerformanceScenario) -> None:
    if not 0 < scenario.accuracy <= 100:
        raise PerformanceScenarioError("acc 必须大于 0 且不超过 100")
    if scenario.misses < 0:
        raise PerformanceScenarioError("miss 不能小于 0")
    if scenario.combo is not None and scenario.combo < 0:
        raise PerformanceScenarioError("combo 不能小于 0")
    if scenario.clock_rate is not None and not 0.5 <= scenario.clock_rate <= 2.0:
        raise PerformanceScenarioError("rate 仅支持 0.5 到 2.0")


def _serialize_mods(mods: Iterable[Mod | str]) -> list[str | dict]:
    result: list[str | dict] = []
    for mod in mods:
        if isinstance(mod, str):
            result.append(mod.upper())
        else:
            result.append(
                {
                    "acronym": mod.acronym.upper(),
                    **({"settings": mod.settings} if mod.settings else {}),
                }
            )
    return result


def calculate_performance_scenarios(
    path: str | Path,
    mode: int,
    mods: Iterable[Mod | str],
    scenarios: Sequence[PerformanceScenario],
) -> tuple[PerformancePoint, ...]:
    """Calculate several scenarios while sharing decoded map and difficulty data."""
    if not scenarios:
        return ()
    if not 0 <= mode < len(GAME_MODES):
        raise PerformanceScenarioError(f"不支持模式 {mode}")

    for scenario in scenarios:
        _validate_scenario_values(scenario)
    first = scenarios[0]
    if any(scenario.clock_rate != first.clock_rate for scenario in scenarios):
        raise PerformanceScenarioError("同一批 PP 情景必须使用相同 rate")

    serialized_mods = _serialize_mods(mods)
    beatmap = Beatmap(path=str(Path(path).absolute()))
    target_mode = GAME_MODES[mode]
    if beatmap.mode != target_mode:
        beatmap.convert(target_mode, serialized_mods)
    if beatmap.is_suspicious():
        raise PerformanceScenarioError("这似乎不是一个正常谱面")

    difficulty_options: dict = {"mods": serialized_mods}
    if first.clock_rate is not None:
        difficulty_options["clock_rate"] = first.clock_rate
    difficulty = Difficulty(**difficulty_options).calculate(beatmap)
    max_combo = int(difficulty.max_combo)
    object_count = int(beatmap.n_objects)
    points: list[PerformancePoint] = []
    for scenario in scenarios:
        if scenario.misses > object_count:
            raise PerformanceScenarioError(f"miss 不能超过物件数 {object_count}")
        if scenario.combo is not None and scenario.combo > max_combo:
            raise PerformanceScenarioError(f"combo 不能超过最大连击 {max_combo}")
        performance_options = {
            "mods": serialized_mods,
            "lazer": scenario.lazer,
            "accuracy": scenario.accuracy,
            "misses": scenario.misses,
        }
        if scenario.clock_rate is not None:
            performance_options["clock_rate"] = scenario.clock_rate
        if scenario.combo is not None:
            performance_options["combo"] = scenario.combo
        attributes = Performance(**performance_options).calculate(difficulty)
        points.append(
            PerformancePoint(
                accuracy=scenario.accuracy,
                pp=float(attributes.pp),
                stars=float(difficulty.stars),
                max_combo=max_combo,
            )
        )
    return tuple(points)


def calculate_performance_report(
    path: str | Path,
    mode: int,
    mods: Iterable[Mod | str],
    scenario: PerformanceScenario,
) -> PerformanceReport:
    accuracies = sorted({*SCENARIO_ACCURACIES, scenario.accuracy})
    scenarios = tuple(scenario.with_accuracy(accuracy) for accuracy in accuracies)
    points = calculate_performance_scenarios(path, mode, mods, scenarios)
    requested = points[accuracies.index(scenario.accuracy)]
    return PerformanceReport(scenario=scenario, requested=requested, points=points)


def format_scenario(scenario: PerformanceScenario, max_combo: int | None = None) -> str:
    combo = scenario.combo if scenario.combo is not None else max_combo
    parts = [f"{scenario.accuracy:g}%", f"{scenario.misses} miss"]
    if combo is not None:
        parts.append(f"{combo}x")
    if scenario.clock_rate is not None:
        parts.append(f"{scenario.clock_rate:g}x rate")
    parts.append("lazer" if scenario.lazer else "stable")
    return " · ".join(parts)
