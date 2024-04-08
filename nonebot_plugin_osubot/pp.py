import math
from rosu_pp_py import Beatmap, Performance, PerformanceAttributes, GameMode
from .schema import Score
from .mods import calc_mods


def cal_pp(score: Score, path: str) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    if score.mode_int == 0:
        mode = GameMode.Osu
    elif score.mode_int == 1:
        mode = GameMode.Taiko
    elif score.mode_int == 2:
        mode = GameMode.Catch
    else:
        mode = GameMode.Mania
    beatmap.convert(mode)
    mods = calc_mods(score.mods)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    if score.mode_int == 2:
        c = Performance(
            accuracy=score.accuracy * 100,
            n_katu=score.statistics.count_katu,
            combo=score.max_combo,
            misses=score.statistics.count_miss,
            n100=score.statistics.count_100,
            n300=score.statistics.count_300,
            mods=mods,
        )
    else:
        c = Performance(
            accuracy=score.accuracy * 100,
            n_katu=score.statistics.count_katu if score.statistics.count_katu else 0,
            n_geki=score.statistics.count_geki if score.statistics.count_geki else 0,
            combo=score.max_combo,
            misses=score.statistics.count_miss if score.statistics.count_miss else 0,
            n50=score.statistics.count_50 if score.statistics.count_50 else 0,
            n100=score.statistics.count_100 if score.statistics.count_100 else 0,
            n300=score.statistics.count_300 if score.statistics.count_300 else 0,
            mods=mods,
        )
    return c.calculate(beatmap)


def get_if_pp_ss_pp(score: Score, path: str) -> tuple:
    beatmap = Beatmap(path=path)
    if score.mode_int == 0:
        mode = GameMode.Osu
    elif score.mode_int == 1:
        mode = GameMode.Taiko
    elif score.mode_int == 2:
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
        n_katu=score.statistics.count_katu if score.statistics.count_katu else 0,
        n_geki=score.statistics.count_geki if score.statistics.count_geki else 0,
        n50=score.statistics.count_50 if score.statistics.count_50 else 0,
        n100=score.statistics.count_100 if score.statistics.count_100 else 0,
        n300=score.statistics.count_300 + score.statistics.count_miss,
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
