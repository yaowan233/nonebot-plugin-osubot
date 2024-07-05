import math

from rosu_pp_py import Beatmap, Strains, GameMode, Performance, PerformanceAttributes

from .mods import calc_mods
from .schema import NewScore
from .schema.score import Mod


def cal_pp(score: NewScore, path: str) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    convert_mode(score, beatmap)
    mods = calc_mods(score.mods)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    if score.ruleset_id == 2:
        c = Performance(
            accuracy=score.accuracy * 100,
            n_katu=score.statistics.small_tick_miss,
            combo=score.max_combo,
            misses=score.statistics.miss,
            n100=score.statistics.large_tick_hit,
            n300=score.statistics.great,
            mods=mods,
        )
    else:
        c = Performance(
            accuracy=score.accuracy * 100,
            n_katu=score.statistics.good,
            n_geki=score.statistics.perfect,
            combo=score.max_combo,
            misses=score.statistics.miss,
            n50=score.statistics.meh,
            n100=score.statistics.ok,
            n300=score.statistics.great,
            mods=mods,
        )
    adjust_performance(score.mods, c)
    return c.calculate(beatmap)


def get_if_pp_ss_pp(score: NewScore, path: str) -> tuple:
    beatmap = Beatmap(path=path)
    convert_mode(score, beatmap)
    mods = calc_mods(score.mods)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    total = beatmap.n_objects
    passed = score.statistics.great + score.statistics.miss + score.statistics.ok + score.statistics.meh
    n300 = score.statistics.great + total - passed
    count_hits = total - score.statistics.miss
    ratio = 1 - n300 / count_hits
    new100s = int(ratio * score.statistics.miss)
    n300 += score.statistics.miss - new100s
    n100 = new100s + score.statistics.ok
    c = Performance(
        # accuracy=score.accuracy * 100,
        # n_katu=score.statistics.small_tick_miss or score.statistics.good or 0,
        # n_geki=score.statistics.perfect or 0,
        n50=score.statistics.meh,
        n100=n100,
        n300=n300,
        mods=mods,
    )
    adjust_performance(score.mods, c)
    if_pp = c.calculate(beatmap).pp
    c = Performance(accuracy=100, mods=mods)
    adjust_performance(score.mods, c)
    ss_pp = c.calculate(beatmap).pp
    if math.isnan(if_pp):
        return "nan", "nan"
    return str(int(round(if_pp, 0))), str(int(round(ss_pp, 0)))


def get_ss_pp(path: str, mods: int) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    c = Performance(accuracy=100, mods=mods)
    ss_pp_info = c.calculate(beatmap)
    return ss_pp_info


def get_strains(path: str, mods: int) -> Strains:
    beatmap = Beatmap(path=path)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    c = Performance(accuracy=100, mods=mods)
    strains = c.difficulty().strains(beatmap)
    return strains


def adjust_performance(mods: list[Mod], c: Performance):
    for mod in mods:
        if mod.acronym == "DT" and mod.settings:
            c.set_clock_rate(mod.settings.speed_change)
        if mod.acronym == "DA" and mod.settings:
            if mod.settings.circle_size is not None:
                c.set_cs(mod.settings.circle_size, False)
            if mod.settings.approach_rate is not None:
                c.set_ar(mod.settings.approach_rate, False)
            if mod.settings.drain_rate is not None:
                c.set_hp(mod.settings.drain_rate, False)
            if mod.settings.overall_difficulty is not None:
                c.set_od(mod.settings.overall_difficulty, False)


def convert_mode(score: NewScore, beatmap: Beatmap):
    if score.ruleset_id == 0:
        mode = GameMode.Osu
    elif score.ruleset_id == 1:
        mode = GameMode.Taiko
    elif score.ruleset_id == 2:
        mode = GameMode.Catch
    else:
        mode = GameMode.Mania
    beatmap.convert(mode)
