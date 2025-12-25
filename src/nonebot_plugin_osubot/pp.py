from rosu_pp_py import Beatmap, Strains, Performance
from osu_tools import OsuCalculator, CalculationResult

from .exceptions import NetworkError
from .schema.score import UnifiedScore


def cal_pp(score: UnifiedScore, path: str) -> CalculationResult:
    beatmap = Beatmap(path=path)
    if beatmap.is_suspicious():
        raise NetworkError("这似乎不是一个正常谱面 OAO")
    c = OsuCalculator()
    res = c.calculate(
        path,
        score.ruleset_id % 4,
        score.mods,
        score.accuracy,
        score.max_combo,
        legacy_total_score=score.legacy_total_score,
        statistics=score.statistics,
    )
    return res


def get_if_pp_ss_pp(score: UnifiedScore, path: str) -> tuple:
    beatmap = Beatmap(path=path)
    if beatmap.is_suspicious():
        return "nan", "nan"
    c = OsuCalculator()
    total = beatmap.n_objects
    score = score.model_copy(deep=True)
    passed = score.statistics.great + score.statistics.miss + score.statistics.ok + score.statistics.meh
    n300 = score.statistics.great + total - passed
    count_hits = total - score.statistics.miss
    ratio = 1 - n300 / count_hits
    new100s = int(ratio * score.statistics.miss)
    n300 += score.statistics.miss - new100s
    n100 = new100s + score.statistics.ok
    n300 = max(n300, 0)  # 确保n300不会为负数 只有在 std 需要计算正确的 ifpp
    score.statistics.miss = 0
    score.statistics.ok = n100
    score.statistics.great = n300
    if_pp = c.calculate(
        path,
        score.ruleset_id % 4,
        score.mods,
        score.accuracy,
        legacy_total_score=score.legacy_total_score,
        statistics=score.statistics,
    ).pp
    ss_pp = c.calculate(path, score.ruleset_id % 4, score.mods, 100).pp
    return str(int(round(if_pp, 0))), str(int(round(ss_pp, 0)))


def get_ss_pp(path: str, ruleset_id: int, mods: list[str]) -> CalculationResult:
    beatmap = Beatmap(path=path)
    if beatmap.is_suspicious():
        raise NetworkError("这似乎不是一个正常谱面 OAO")
    c = OsuCalculator()
    res = c.calculate(path, ruleset_id % 4, acc=100, mods=mods)
    return res


def get_strains(path: str, mods: int) -> Strains:
    beatmap = Beatmap(path=path)
    c = Performance(accuracy=100, mods=mods)
    strains = c.difficulty().strains(beatmap)
    return strains
