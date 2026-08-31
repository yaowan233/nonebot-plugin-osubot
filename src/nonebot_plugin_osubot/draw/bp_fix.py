from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO

from nonebot.log import logger

from ..api import get_server, get_user_info_data, get_user_scores
from ..exceptions import NetworkError
from ..server import GameServer, ModeVariant, ServerFeature
from ..file import ensure_osu_file, get_pfm_img, map_path
from ..performance import PerformanceScenario, calculate_performance_scenarios
from ..schema.score import UnifiedScore
from .bp_fix_svg import render_bp_fix_svg
from .score import _player_avatar_data_uri
from .svg_render import thumbnail_data_uri


BP_WEIGHT = 0.95
MAX_FIX_ENTRIES = 12
CALCULATION_CONCURRENCY = 4


@dataclass(frozen=True, slots=True)
class FixedCandidate:
    index: int
    fixed_pp: float
    max_combo: int
    stars: float = 0.0


def _object_count(score: UnifiedScore) -> int:
    beatmap = score.beatmap
    if beatmap is not None:
        count = sum(int(value or 0) for value in (beatmap.count_circles, beatmap.count_sliders, beatmap.count_spinners))
        if count:
            return count
    statistics = score.statistics
    fields = ("great", "ok", "meh", "miss")
    if score.ruleset_id % 4 == 2:
        fields = ("great", "large_tick_hit", "small_tick_hit", "small_tick_miss", "miss")
    elif score.ruleset_id % 4 == 3:
        fields = ("perfect", "great", "good", "ok", "meh", "miss")
    return sum(int(getattr(statistics, field, 0) or 0) for field in fields)


def is_fix_candidate(score: UnifiedScore) -> bool:
    """Return whether a BP is a small enough choke to include in BP Fix."""
    if not score.passed or score.beatmap is None or score.pp is None:
        return False
    if score.rank.upper() in {"X", "XH"}:
        return False

    misses = int(score.statistics.miss or 0)
    if misses:
        object_count = _object_count(score)
        return object_count > 0 and misses / object_count <= 0.01

    map_max_combo = score.beatmap.max_combo
    return map_max_combo is None or score.max_combo < map_max_combo


async def _calculate_fixed_candidate(
    index: int,
    score: UnifiedScore,
    semaphore: asyncio.Semaphore,
    server: GameServer,
    requested_lazer: bool,
) -> FixedCandidate | None:
    beatmap = score.beatmap
    if beatmap is None:
        return None
    async with semaphore:
        try:
            osu_file = await ensure_osu_file(beatmap.set_id, beatmap.id, beatmap.checksum)
            point = (
                await asyncio.to_thread(
                    calculate_performance_scenarios,
                    osu_file,
                    score.ruleset_id % 4,
                    score.mods,
                    [
                        PerformanceScenario(
                            accuracy=score.accuracy,
                            misses=0,
                            combo=None,
                            lazer=server.descriptor.score_uses_lazer(
                                score.score_version,
                                requested_lazer,
                            ),
                        )
                    ],
                )
            )[0]
        except Exception as error:
            logger.debug(f"BP Fix 跳过谱面 {beatmap.id}: {error}")
            return None
    if int(score.statistics.miss or 0) == 0 and score.max_combo >= point.max_combo:
        return None
    return FixedCandidate(index=index, fixed_pp=point.pp, max_combo=point.max_combo, stars=point.stars)


def _weighted_pp(values: list[float]) -> float:
    return sum(value * BP_WEIGHT**index for index, value in enumerate(values))


def build_bp_fix_payload(
    info,
    scores: list[UnifiedScore],
    fixed: list[FixedCandidate],
    avatar_data: str | None,
) -> dict:
    fixed_by_index = {item.index: item for item in fixed}
    original_pp = [float(score.pp or 0) for score in scores]
    hypothetical = [
        (
            max(original_pp[index], fixed_by_index[index].fixed_pp) if index in fixed_by_index else original_pp[index],
            index,
        )
        for index in range(len(scores))
    ]
    hypothetical.sort(key=lambda item: item[0], reverse=True)
    new_rank = {original_index: rank for rank, (_pp, original_index) in enumerate(hypothetical, start=1)}
    weighted_gain = _weighted_pp([item[0] for item in hypothetical]) - _weighted_pp(original_pp)
    current_total = float(info.statistics.pp) if info.statistics else _weighted_pp(original_pp)

    entries = []
    for candidate in fixed:
        score = scores[candidate.index]
        old_pp = original_pp[candidate.index]
        if candidate.fixed_pp <= old_pp + 0.05 or score.beatmap is None:
            continue
        mods = [mod.acronym.upper() for mod in score.mods]
        if "NC" in mods and "DT" in mods:
            mods.remove("DT")
        entries.append(
            {
                "old_rank": candidate.index + 1,
                "new_rank": new_rank[candidate.index],
                "title": score.beatmap.title,
                "artist": score.beatmap.artist,
                "version": score.beatmap.version,
                "map_id": score.beatmap.id,
                "set_id": score.beatmap.set_id,
                "stars": candidate.stars or getattr(score.beatmap, "stars", 0),
                "mods": mods,
                "accuracy": score.accuracy,
                "misses": int(score.statistics.miss or 0),
                "combo": score.max_combo,
                "max_combo": candidate.max_combo,
                "old_pp": old_pp,
                "fixed_pp": candidate.fixed_pp,
                "gain": candidate.fixed_pp - old_pp,
                "date": score.ended_at.strftime("%Y.%m.%d") if getattr(score, "ended_at", None) else "",
                "score_version": getattr(score, "score_version", None),
                "cover_data": None,
            }
        )
    entries.sort(key=lambda item: item["gain"], reverse=True)
    entries = entries[:MAX_FIX_ENTRIES]
    if not entries:
        raise NetworkError("BP 中没有符合条件的可修复掉连成绩")

    statistics = info.statistics
    if hasattr(statistics, "model_dump"):
        statistics = statistics.model_dump()
    elif statistics is not None:
        statistics = {"pp": getattr(statistics, "pp", current_total)}
    return {
        "mode": scores[0].ruleset_id % 4 if scores else 0,
        "section_title": "BP FIX",
        "user": {
            "id": info.id,
            "name": info.username,
            "country": info.country_code,
            "avatar_data": avatar_data,
            "support_level": getattr(info, "support_level", 0),
            "statistics": statistics or {},
            "team": None,
        },
        "current_pp": current_total,
        "fixed_pp": current_total + max(0.0, weighted_gain),
        "gain": max(0.0, weighted_gain),
        "candidate_count": len(fixed),
        "entries": entries,
    }


async def draw_bp_fix(
    uid: int,
    is_lazer: bool,
    mode: str,
    source: str = "osu",
) -> BytesIO:
    server = get_server(source)
    play_mode = server.parse_mode(mode)
    if not server.supports(ServerFeature.BP_FIX, play_mode):
        if play_mode.variant != ModeVariant.STANDARD:
            raise NetworkError("BP Fix 暂不支持私服 RX/AP 模式的专用 PP 算法")
        raise NetworkError(f"{server.label} 暂不支持 BP Fix")
    info, scores = await asyncio.gather(
        get_user_info_data(uid, mode, source),
        get_user_scores(uid, mode, "best", source=source, legacy_only=not is_lazer, limit=100),
    )
    if not scores:
        raise NetworkError("未查询到 BP 成绩")

    candidate_scores = [(index, score) for index, score in enumerate(scores) if is_fix_candidate(score)]
    if not candidate_scores:
        raise NetworkError("BP 中没有符合条件的可修复掉连成绩")
    semaphore = asyncio.Semaphore(CALCULATION_CONCURRENCY)
    results = await asyncio.gather(
        *(_calculate_fixed_candidate(index, score, semaphore, server, is_lazer) for index, score in candidate_scores)
    )
    fixed = [result for result in results if result is not None]
    payload = build_bp_fix_payload(info, scores, fixed, None)
    cover_paths = [map_path / str(entry["set_id"]) / "cover.jpg" for entry in payload["entries"]]
    cover_tasks = [
        get_pfm_img(
            f"https://assets.ppy.sh/beatmaps/{entry['set_id']}/covers/cover.jpg",
            cover_path,
        )
        for entry, cover_path in zip(payload["entries"], cover_paths)
        if not cover_path.exists()
    ]
    _, avatar_data = await asyncio.gather(
        asyncio.gather(*cover_tasks),
        _player_avatar_data_uri(info, source),
    )
    payload["user"]["avatar_data"] = avatar_data
    for entry, cover_path in zip(payload["entries"], cover_paths):
        if cover_path.exists():
            entry["cover_data"] = thumbnail_data_uri(cover_path, max_width=320, max_height=180)
    return await render_bp_fix_svg(payload)
