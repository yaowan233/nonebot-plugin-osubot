import math

from rosu_pp_py import Beatmap, Performance, PerformanceAttributes, GameMode, Strains

from .mods import calc_mods, calc_old_mods
from .schema import NewScore, Score


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
    for mod in score.mods:
        if mod["acronym"] == "DT" and mod.get("settings"):
            c.set_clock_rate(mod["settings"]["speed_change"])
        if mod["acronym"] == "DA" and mod.get("settings"):
            if mod["settings"].get("circle_size") is not None:
                c.set_cs(mod["settings"]["circle_size"], False)
            if mod["settings"].get("approach_rate") is not None:
                c.set_ar(mod["settings"]["approach_rate"], False)
            if mod["settings"].get("drain_rate") is not None:
                c.set_hp(mod["settings"]["drain_rate"], False)
            if mod["settings"].get("overall_difficulty") is not None:
                c.set_od(mod["settings"]["overall_difficulty"], False)
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
    for mod in score.mods:
        if mod["acronym"] == "DT" and mod.get("settings"):
            c.set_clock_rate(mod["settings"]["speed_change"])
        if mod["acronym"] == "DA" and mod.get("settings"):
            if mod["settings"].get("circle_size") is not None:
                c.set_cs(mod["settings"]["circle_size"], False)
            if mod["settings"].get("approach_rate") is not None:
                c.set_ar(mod["settings"]["approach_rate"], False)
            if mod["settings"].get("drain_rate") is not None:
                c.set_hp(mod["settings"]["drain_rate"], False)
            if mod["settings"].get("overall_difficulty") is not None:
                c.set_od(mod["settings"]["overall_difficulty"], False)
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


def cal_old_pp(score: Score, path: str) -> PerformanceAttributes:
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
    mods = calc_old_mods(score.mods)
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
