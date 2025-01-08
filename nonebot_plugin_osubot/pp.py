import math
import importlib.metadata

from rosu_pp_py import Beatmap, Strains, GameMode, Performance, PerformanceAttributes

from .schema.score import UnifiedScore

is_v2 = importlib.metadata.version("pydantic").startswith("2")


def cal_pp(score: UnifiedScore, path: str, is_lazer: bool) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    convert_mode(score, beatmap)
    c = Performance(
        accuracy=score.accuracy,
        n_katu=score.statistics.good,
        n_geki=score.statistics.perfect,
        combo=score.max_combo,
        misses=score.statistics.miss,
        n50=score.statistics.meh,
        n100=score.statistics.ok,
        n300=score.statistics.great,
        small_tick_hits=score.statistics.small_tick_hit,
        large_tick_hits=score.statistics.large_tick_hit,
        slider_end_hits=score.statistics.slider_tail_hit,
        mods=[mod.model_dump() for mod in score.mods] if is_v2 else [mod.dict() for mod in score.mods],
        lazer=cal_lazer(score, is_lazer),
    )
    return c.calculate(beatmap)


def get_if_pp_ss_pp(score: UnifiedScore, path: str, is_lazer: bool) -> tuple:
    beatmap = Beatmap(path=path)
    convert_mode(score, beatmap)
    total = beatmap.n_objects
    passed = score.statistics.great + score.statistics.miss + score.statistics.ok + score.statistics.meh
    n300 = score.statistics.great + total - passed
    count_hits = total - score.statistics.miss
    ratio = 1 - n300 / count_hits
    new100s = int(ratio * score.statistics.miss)
    n300 += score.statistics.miss - new100s
    n100 = new100s + score.statistics.ok
    n300 = max(n300, 0)  # 确保n300不会为负数 只有在 std 需要计算正确的 ifpp
    c = Performance(
        n50=score.statistics.meh,
        n100=n100,
        n300=n300,
        mods=[mod.model_dump() for mod in score.mods] if is_v2 else [mod.dict() for mod in score.mods],
        lazer=cal_lazer(score, is_lazer),
    )
    if_pp = c.calculate(beatmap).pp
    c = Performance(
        accuracy=100,
        mods=[mod.model_dump() for mod in score.mods] if is_v2 else [mod.dict() for mod in score.mods],
        lazer=is_lazer,
    )
    ss_pp = c.calculate(beatmap).pp
    if math.isnan(if_pp):
        return "nan", "nan"
    return str(int(round(if_pp, 0))), str(int(round(ss_pp, 0)))


def get_ss_pp(path: str, mods: int, is_lazer) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    c = Performance(accuracy=100, mods=mods, lazer=is_lazer)
    ss_pp_info = c.calculate(beatmap)
    return ss_pp_info


def get_strains(path: str, mods: int) -> Strains:
    beatmap = Beatmap(path=path)
    c = Performance(accuracy=100, mods=mods)
    strains = c.difficulty().strains(beatmap)
    return strains


def convert_mode(score: UnifiedScore, beatmap: Beatmap):
    if score.ruleset_id in {0, 4, 8}:
        mode = GameMode.Osu
    elif score.ruleset_id in {1, 5}:
        mode = GameMode.Taiko
    elif score.ruleset_id in {2, 6}:
        mode = GameMode.Catch
    else:
        mode = GameMode.Mania
    beatmap.convert(mode)


def cal_lazer(score: UnifiedScore, is_lazer: bool):
    return is_lazer and not any(mod.acronym == "CL" for mod in score.mods)
