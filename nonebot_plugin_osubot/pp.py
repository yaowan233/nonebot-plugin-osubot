from rosu_pp_py import Beatmap, Calculator, PerformanceAttributes
from .schema import Score
from .mods import calc_mods


def cal_pp(score: Score, path: str) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    mods = calc_mods(score.mods)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    c = Calculator(acc=score.accuracy * 100, n_katu=score.statistics.count_katu,
                   n_geki=score.statistics.count_geki, combo=score.max_combo,
                   n_misses=score.statistics.count_miss,
                   n50=score.statistics.count_50,
                   n100=score.statistics.count_100,
                   n300=score.statistics.count_300,
                   mods=mods)
    return c.performance(beatmap)


def get_if_pp_ss_pp(score: Score, path: str) -> tuple:
    beatmap = Beatmap(path=path)
    mods = calc_mods(score.mods)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    c = Calculator(acc=score.accuracy * 100, n_katu=score.statistics.count_katu,
                   n_geki=score.statistics.count_geki, combo=score.max_combo,
                   n_misses=0,
                   n50=score.statistics.count_50,
                   n100=score.statistics.count_100,
                   n300=score.statistics.count_300,
                   mods=mods)
    if_pp = c.performance(beatmap).pp
    c = Calculator(acc=100,
                   mods=mods)
    ss_pp = c.performance(beatmap).pp
    return int(round(if_pp, 0)), int(round(ss_pp, 0))


def get_ss_pp(path: str, mods: int) -> PerformanceAttributes:
    beatmap = Beatmap(path=path)
    if mods & (1 << 9):
        mods -= 1 << 9
        mods += 1 << 6
    c = Calculator(acc=100, mods=mods)
    ss_pp_info = c.performance(beatmap)
    return ss_pp_info
