import json
import threading
from functools import lru_cache
from pathlib import Path

from rosu_pp_py import Beatmap, Difficulty, GameMode, Performance, Strains
from osu_tools import OsuCalculator, CalculationResult
from nonebot.log import logger

from .exceptions import NetworkError
from .schema.score import Mod, UnifiedScore


PPYSB_RELAX_RULESETS = {4, 5, 6}
RELAX_MODS = {"RX", "RX2", "AP"}

# osu-tools supports retaining decoded beatmaps and difficulty attributes, but
# constructing a fresh calculator for every derived value disabled that cache.
# A score card calculates the same map/mod combination several times (current,
# FC, SS and target accuracies), so keep one process-local calculator.


class _CachedOsuCalculator(OsuCalculator):
    """Serialize access to shared pythonnet objects while retaining their cache."""

    def __init__(self) -> None:
        self._calculation_lock = threading.RLock()
        super().__init__(prepared_cache_size=128)

    def calculate(self, *args, **kwargs) -> CalculationResult:
        with self._calculation_lock:
            return super().calculate(*args, **kwargs)


_calculator: _CachedOsuCalculator | None = None
_calculator_init_lock = threading.Lock()


def get_osu_calculator() -> OsuCalculator:
    global _calculator
    if _calculator is None:
        with _calculator_init_lock:
            if _calculator is None:
                _calculator = _CachedOsuCalculator()
    return _calculator


def _mod_has_relax(mod: Mod | str) -> bool:
    return (mod.acronym if isinstance(mod, Mod) else str(mod)) in RELAX_MODS


def is_ppysb_relax_score(score: UnifiedScore, source: str) -> bool:
    if source == "ppysb":
        return score.ruleset_id in PPYSB_RELAX_RULESETS
    if source == "g0v0":
        # g0v0 的 RX/AP 成绩 ruleset_id 仍是 0-3，relax 通过 mods 里的 RX/RX2/AP 表达。
        return any(_mod_has_relax(m) for m in score.mods)
    return False


def normalize_mods_for_pp(mods: list[Mod] | list[str], source: str, ruleset_id: int):
    if (source == "ppysb" and ruleset_id in PPYSB_RELAX_RULESETS) or (
        source == "g0v0" and any(_mod_has_relax(m) for m in mods)
    ):
        return [mod for mod in mods if not _mod_has_relax(mod)]
    return mods


def without_relax_mods(score: UnifiedScore) -> UnifiedScore:
    """返回移除了 RX/AP 系 mod 的成绩深拷贝，用于推演非 relax 的 pp 值。

    g0v0/ppysb 的 RX/AP 成绩 mods 含 RX/RX2/AP，本地 rosu-pp 不支持这些 mod；
    推演（96%/98% ACC、IF FC、SS PP）时移除后按普通规则计算，得到该谱面
    不带 relax 的 pp 值（如 HDHRRX 成绩显示 HDHR 的推演）。
    始终返回副本，避免推演函数改写原成绩的 statistics。
    """
    mods = score.mods
    copy = score.model_copy(deep=True)
    if any((m.acronym if isinstance(m, Mod) else str(m)) in RELAX_MODS for m in mods):
        copy.mods = [
            m for m in copy.mods if (m.acronym if isinstance(m, Mod) else str(m)) not in RELAX_MODS
        ]
    return copy


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
    c = get_osu_calculator()
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


@lru_cache(maxsize=1024)
def _cal_stars_cached(
    path: str,
    modified_ns: int,
    file_size: int,
    mode: int,
    mods_json: str,
) -> float:
    del modified_ns, file_size  # They are part of the cache key for revision invalidation.
    mods = json.loads(mods_json)
    beatmap = Beatmap(path=path)
    target_mode = (GameMode.Osu, GameMode.Taiko, GameMode.Catch, GameMode.Mania)[mode]
    if beatmap.mode != target_mode:
        beatmap.convert(target_mode, mods)
    return float(Difficulty(mods=mods).calculate(beatmap).stars)


def cal_stars(score: UnifiedScore, path: str, source: str = "osu") -> float:
    """Calculate only the modded star rating with the native rosu-pp binding.

    Score-list renderers already receive the official PP value from the API.
    Using osu-tools there would calculate performance again and serialize all
    list entries behind its shared pythonnet lock, while only difficulty is
    needed for display.
    """
    score = normalize_score_for_pp(score, source)
    mods = [
        {
            "acronym": mod.acronym,
            **({"settings": mod.settings} if mod.settings else {}),
        }
        for mod in score.mods
    ]
    resolved = Path(path).resolve()
    stat = resolved.stat()
    mods_json = json.dumps(mods, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return _cal_stars_cached(
        str(resolved),
        stat.st_mtime_ns,
        stat.st_size,
        score.ruleset_id % 4,
        mods_json,
    )


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
    c = get_osu_calculator()
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
    c = get_osu_calculator()
    mods = normalize_mods_for_pp(mods, source, ruleset_id)
    res = c.calculate(path, ruleset_id % 4, acc=100, mods=mods)
    return res


def get_strains(path: str, mods: int) -> Strains:
    beatmap = Beatmap(path=path)
    c = Performance(accuracy=100, mods=mods)
    strains = c.difficulty().strains(beatmap)
    return strains


async def warm_up_pp_calculator():
    """后台预热 pp 计算器：osu_tools/rosu_pp 首次调用有近 2s 初始化开销，提前到启动时完成。"""
    import asyncio

    from .file import map_path

    try:
        osu_files = sorted(map_path.glob("*/*.osu"))
        if not osu_files:
            return
        path = str(osu_files[0].absolute())

        def _warm():
            Beatmap(path=path)
            get_osu_calculator().calculate(path, 0, [], 100)

        await asyncio.to_thread(_warm)
    except Exception as e:
        logger.debug(f"pp 计算器预热失败（不影响使用）: {e}")
