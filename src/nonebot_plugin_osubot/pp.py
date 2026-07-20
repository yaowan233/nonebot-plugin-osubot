from rosu_pp_py import Beatmap, GameMode, Strains, Performance
from osu_tools import OsuCalculator, CalculationResult

from .exceptions import NetworkError
from .schema.score import Mod, UnifiedScore


PPYSB_RELAX_RULESETS = {4, 5, 6}
RELAX_MODS = {"RX", "RX2"}


def is_ppysb_relax_score(score: UnifiedScore, source: str) -> bool:
    return source == "ppysb" and score.ruleset_id in PPYSB_RELAX_RULESETS


def normalize_mods_for_pp(mods: list[Mod] | list[str], source: str, ruleset_id: int):
    if source == "ppysb" and ruleset_id in PPYSB_RELAX_RULESETS:
        return [mod for mod in mods if (mod if isinstance(mod, str) else mod.acronym) not in RELAX_MODS]
    return mods


def normalize_score_for_pp(score: UnifiedScore, source: str = "osu") -> UnifiedScore:
    if not is_ppysb_relax_score(score, source):
        return score
    score = score.model_copy(deep=True)
    score.mods = normalize_mods_for_pp(score.mods, source, score.ruleset_id)
    return score


def cal_pp(score: UnifiedScore, path: str, source: str = "osu") -> CalculationResult:
    beatmap = Beatmap(path=path)
    if beatmap.is_suspicious():
        raise NetworkError("这似乎不是一个正常谱面 OAO")
    score = normalize_score_for_pp(score, source)
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


def get_pp_components(score: UnifiedScore, path: str, source: str = "osu") -> dict[str, float]:
    """Return the mode-specific pp portions exposed by rosu-pp.

    osu!catch has a single performance value rather than additive pp portions;
    it is returned as ``catch`` so the renderer can describe it accurately.
    """
    score = normalize_score_for_pp(score, source)
    mode = score.ruleset_id % 4
    mods = [{"acronym": mod.acronym, **({"settings": mod.settings} if mod.settings else {})} for mod in score.mods]
    beatmap = Beatmap(path=path)
    target_mode = (GameMode.Osu, GameMode.Taiko, GameMode.Catch, GameMode.Mania)[mode]
    if beatmap.mode != target_mode:
        beatmap.convert(target_mode, mods)

    stats = score.statistics
    kwargs = {
        "mods": mods,
        "accuracy": score.accuracy,
        "misses": stats.miss or 0,
    }
    if mode != 3:
        kwargs["combo"] = score.max_combo
    if mode == 0:
        kwargs.update(n300=stats.great or 0, n100=stats.ok or 0, n50=stats.meh or 0)
    elif mode == 1:
        kwargs.update(n300=stats.great or 0, n100=stats.ok or 0)
    elif mode == 2:
        kwargs.update(
            n300=stats.great or 0,
            n100=stats.large_tick_hit or 0,
            n_katu=stats.small_tick_miss or 0,
        )
    else:
        kwargs.update(
            n_geki=stats.perfect or 0,
            n300=stats.great or 0,
            n_katu=stats.good or 0,
            n100=stats.ok or 0,
            n50=stats.meh or 0,
        )

    attributes = Performance(**kwargs).calculate(beatmap)
    return {
        "aim": attributes.pp_aim or 0.0,
        "speed": attributes.pp_speed or 0.0,
        "accuracy": attributes.pp_accuracy or 0.0,
        "flashlight": attributes.pp_flashlight or 0.0,
        "difficulty": attributes.pp_difficulty or 0.0,
        "catch": attributes.pp,
    }


def get_if_pp_ss_pp(score: UnifiedScore, path: str, source: str = "osu") -> tuple:
    beatmap = Beatmap(path=path)
    if beatmap.is_suspicious():
        return "nan", "nan"
    c = OsuCalculator()
    total = beatmap.n_objects
    score = normalize_score_for_pp(score, source)
    if not is_ppysb_relax_score(score, source):
        score = score.model_copy(deep=True)
    if score.ruleset_id % 4 == 2:
        missed_fruits = score.statistics.miss or 0
        score.statistics.great = (score.statistics.great or 0) + missed_fruits
        score.statistics.miss = 0
        caught = (
            (score.statistics.great or 0)
            + (score.statistics.large_tick_hit or 0)
            + (score.statistics.small_tick_hit or 0)
        )
        total_catchables = caught + (score.statistics.small_tick_miss or 0)
        fc_accuracy = caught / total_catchables * 100 if total_catchables else 100
        if_pp = c.calculate(
            path,
            score.ruleset_id % 4,
            score.mods,
            fc_accuracy,
            statistics=score.statistics,
        ).pp
        ss_pp = c.calculate(path, score.ruleset_id % 4, score.mods, 100).pp
        return str(int(round(if_pp, 0))), str(int(round(ss_pp, 0)))
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


def get_ss_pp(path: str, ruleset_id: int, mods: list[str], source: str = "osu") -> CalculationResult:
    beatmap = Beatmap(path=path)
    if beatmap.is_suspicious():
        raise NetworkError("这似乎不是一个正常谱面 OAO")
    c = OsuCalculator()
    mods = normalize_mods_for_pp(mods, source, ruleset_id)
    res = c.calculate(path, ruleset_id % 4, acc=100, mods=mods)
    return res


def get_strains(path: str, mods: int) -> Strains:
    beatmap = Beatmap(path=path)
    c = Performance(accuracy=100, mods=mods)
    strains = c.difficulty().strains(beatmap)
    return strains
