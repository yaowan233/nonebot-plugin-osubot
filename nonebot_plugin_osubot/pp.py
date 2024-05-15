import math
from rosu_pp_py import Beatmap, Performance, PerformanceAttributes, GameMode
from .schema import NewScore
from .mods import calc_mods


def cal_pp(score: NewScore, path: str) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    if score.ruleset_id == 0:
        mode = GameMode.Osu
    elif score.ruleset_id == 1:
        mode = GameMode.Taiko
    elif score.ruleset_id == 2:
        mode = GameMode.Catch
    else:
        mode = GameMode.Mania
    beatmap.convert(mode)
    mods = calc_mods(score.mods)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    if score.ruleset_id == 2:
        c = Performance(
            accuracy=score.accuracy * 100,
            n_katu=score.statistics.small_tick_miss or 0,
            combo=score.max_combo,
            misses=score.statistics.miss or 0,
            n100=score.statistics.large_tick_hit or 0,
            n300=score.statistics.great or 0,
            mods=mods,
        )
    else:
        c = Performance(
            accuracy=score.accuracy * 100,
            n_katu=score.statistics.good or 0,
            n_geki=score.statistics.perfect or 0,
            combo=score.max_combo,
            misses=score.statistics.miss or 0,
            n50=score.statistics.meh or 0,
            n100=score.statistics.ok or 0,
            n300=score.statistics.great or 0,
            mods=mods,
        )
    return c.calculate(beatmap)


def get_if_pp_ss_pp(score: NewScore, path: str) -> tuple:
    beatmap = Beatmap(path=path)
    if score.ruleset_id == 0:
        mode = GameMode.Osu
    elif score.ruleset_id == 1:
        mode = GameMode.Taiko
    elif score.ruleset_id == 2:
        mode = GameMode.Catch
    else:
        mode = GameMode.Mania
    beatmap.convert(mode)
    mods = calc_mods(score.mods)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    c = Performance(
        accuracy=score.accuracy * 100,
        n_katu=score.statistics.small_tick_miss or score.statistics.good or 0,
        n_geki=score.statistics.perfect or 0,
        n50=score.statistics.meh or 0,
        n100=score.statistics.large_tick_hit or score.statistics.ok or 0,
        n300=(score.statistics.great or 0) + (score.statistics.miss or 0),
        mods=mods,
    )
    if_pp = c.calculate(beatmap).pp
    c = Performance(accuracy=100, mods=mods)
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
