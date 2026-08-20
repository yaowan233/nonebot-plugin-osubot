import asyncio
import json
import threading
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Union

from nonebot.log import logger

from ..api import get_user_info_data, get_user_scores
from ..exceptions import NetworkError
from ..file import ensure_osu_file, get_pfm_img, map_path
from ..mods import get_mods_list, get_speed_change_labels
from ..pp import cal_pp, cal_stars
from ..schema.score import UnifiedScore
from .bp_svg import render_bp_svg
from .score import _player_avatar_data_uri, _team_icon_data, cal_score_info
from .svg_render import thumbnail_data_uri
from .utils import filter_scores_with_regex


_STAR_RATING_MODS = frozenset({"DT", "NC", "HT", "HR", "EZ", "DC", "DA"})
_CALCULATED_PP_CACHE_MAX_ENTRIES = 1024
_calculated_pp_cache: dict[tuple, float] = {}
_calculated_pp_cache_lock = threading.Lock()


def _has_star_rating_mod(score: UnifiedScore) -> bool:
    return any(mod.acronym.upper() in _STAR_RATING_MODS for mod in score.mods)


def _requires_osu_file(score: UnifiedScore) -> bool:
    return score.pp is None or _has_star_rating_mod(score)


def _calculated_pp(score: UnifiedScore, osu_file, source: str) -> float:
    stat = osu_file.stat()
    statistics = getattr(score, "statistics", None)
    if hasattr(statistics, "model_dump"):
        statistics = statistics.model_dump(mode="json")
    mods = [
        {
            "acronym": mod.acronym,
            **({"settings": mod.settings} if mod.settings else {}),
        }
        for mod in score.mods
    ]
    key = (
        str(osu_file.resolve()),
        stat.st_mtime_ns,
        stat.st_size,
        source,
        getattr(score, "ruleset_id", None),
        json.dumps(mods, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        getattr(score, "accuracy", None),
        getattr(score, "max_combo", None),
        getattr(score, "legacy_total_score", None),
        json.dumps(statistics, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str),
    )
    with _calculated_pp_cache_lock:
        if key in _calculated_pp_cache:
            return _calculated_pp_cache[key]
    value = float(cal_pp(score, str(osu_file.absolute()), source).pp)
    with _calculated_pp_cache_lock:
        if len(_calculated_pp_cache) >= _CALCULATED_PP_CACHE_MAX_ENTRIES:
            _calculated_pp_cache.pop(next(iter(_calculated_pp_cache)))
        _calculated_pp_cache[key] = value
    return value


async def _gather_optional_osu_files(tasks: list) -> None:
    """Download list-only calculation resources without making them fatal."""
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [result for result in results if isinstance(result, BaseException)]
    if failures:
        logger.warning(f"BP 列表有 {len(failures)} 个谱面文件下载失败，已使用 API 数据继续渲染")
        logger.debug(f"BP 列表谱面下载失败详情: {failures!r}")


async def draw_bp(
    project: str,
    uid: int,
    is_lazer: bool,
    mode: str,
    mods: Optional[list],
    low_bound: int,
    high_bound: int,
    day: int,
    search_condition: list,
    source: str,
) -> BytesIO:
    info_task = asyncio.create_task(get_user_info_data(uid, mode, source))
    try:
        scores, selected = await select_bp_scores(
            project,
            uid,
            is_lazer,
            mode,
            mods,
            low_bound,
            high_bound,
            day,
            search_condition,
            source,
        )
        info = await info_task
    except BaseException:
        if not info_task.done():
            info_task.cancel()
        await asyncio.gather(info_task, return_exceptions=True)
        raise
    return await draw_pfm(
        project,
        uid,
        scores,
        selected,
        mode,
        source,
        low_bound,
        high_bound,
        day,
        info=info,
    )


async def select_bp_scores(
    project: str,
    uid: int,
    is_lazer: bool,
    mode: str,
    mods: Optional[list],
    low_bound: int,
    high_bound: int,
    day: int,
    search_condition: list,
    source: str,
) -> tuple[list[UnifiedScore], list[UnifiedScore]]:
    """Fetch and filter BP scores without rendering them."""
    api_limit = high_bound if project in {"bp", "firsts"} and not mods and not search_condition else 200
    scope = "firsts" if project == "firsts" else "best"
    scores = await get_user_scores(
        uid,
        mode,
        scope,
        source=source,
        legacy_only=not is_lazer,
        limit=api_limit,
    )
    candidates = scores
    if project == "tbp":
        cutoff = datetime.now() - timedelta(days=day)
        candidates = [score for score in candidates if score.ended_at > cutoff]
    if mods:
        mods_ls = get_mods_list(candidates, mods)
        if low_bound > len(mods_ls):
            raise NetworkError(f"未找到开启 {'|'.join(mods)} Mods的成绩")
        selected = [candidates[i] for i in mods_ls[low_bound - 1 : high_bound]]
    else:
        selected = candidates[low_bound - 1 : high_bound]
    for index, score in enumerate(selected):
        if score.mods and any(mod.acronym == "NC" for mod in score.mods):
            score.mods = [mod for mod in score.mods if mod.acronym != "DT"]
        selected[index] = cal_score_info(is_lazer, score, source)
    if search_condition:
        selected = filter_scores_with_regex(selected, search_condition)
    if not selected:
        raise NetworkError("未查询到游玩记录")
    return scores, selected


async def draw_pfm(
    project: str,
    uid: int,
    score_ls: list[UnifiedScore],
    score_ls_filtered: list[UnifiedScore],
    mode: str,
    source: str,
    low_bound: int = 0,
    high_bound: int = 0,
    day: int = 0,
    *,
    info=None,
) -> Union[str, BytesIO]:
    if not score_ls_filtered:
        raise NetworkError("未查询到游玩记录")
    cover_paths = [map_path / str(score.beatmap.set_id) / "cover.jpg" for score in score_ls_filtered]
    cover_tasks = [
        get_pfm_img(
            f"https://assets.ppy.sh/beatmaps/{score.beatmap.set_id}/covers/cover.jpg",
            cover_path,
        )
        for score, cover_path in zip(score_ls_filtered, cover_paths)
        if not cover_path.exists()
    ]
    osu_tasks = [
        ensure_osu_file(score.beatmap.set_id, score.beatmap.id, score.beatmap.checksum)
        for score in score_ls_filtered
        if _requires_osu_file(score)
    ]
    resources = [asyncio.gather(*cover_tasks), _gather_optional_osu_files(osu_tasks)]
    if info is None:
        info, *_ = await asyncio.gather(get_user_info_data(uid, mode, source), *resources)
        avatar_data, team_data = await asyncio.gather(
            _player_avatar_data_uri(info, source),
            _team_icon_data(info),
        )
    else:
        _, _, avatar_data, team_data = await asyncio.gather(
            *resources,
            _player_avatar_data_uri(info, source),
            _team_icon_data(info),
        )

    score_indices = {id(score): index for index, score in enumerate(score_ls, start=1)}

    def build_play(score: UnifiedScore, cover_path, fallback_index: int) -> dict:
        osu_file = map_path / str(score.beatmap.set_id) / f"{score.beatmap.id}.osu"
        stars = score.beatmap.stars
        pp = score.pp
        if osu_file.exists() and _has_star_rating_mod(score):
            try:
                stars = cal_stars(score, str(osu_file.absolute()), source)
            except Exception:
                pass
        if pp is None and osu_file.exists():
            try:
                pp = _calculated_pp(score, osu_file, source)
            except Exception:
                pass
        speed_changes = get_speed_change_labels(score.mods)
        mods = [mod.acronym for mod in score.mods]
        if "NC" in mods and "DT" in mods:
            mods.remove("DT")
        bp_index = score_indices.get(id(score), fallback_index)
        return {
            "index": bp_index,
            "title": score.beatmap.title,
            "artist": score.beatmap.artist,
            "version": score.beatmap.version,
            "cover_data": (
                thumbnail_data_uri(cover_path, max_width=256, max_height=145) if cover_path.exists() else None
            ),
            "pp": pp or 0,
            "accuracy": score.accuracy,
            "stars": stars,
            "mods": mods,
            "speed_changes": speed_changes,
            "date": score.ended_at.strftime("%Y.%m.%d"),
            "score_version": getattr(score, "score_version", None) if source == "osu" else None,
        }

    plays = await asyncio.gather(
        *(
            asyncio.to_thread(build_play, score, cover_path, low_bound + index)
            for index, (score, cover_path) in enumerate(zip(score_ls_filtered, cover_paths))
        )
    )

    if project == "bp":
        shown_high = min(high_bound, low_bound + len(score_ls_filtered) - 1)
        section_title = "最佳成绩"
        range_label = f"BP {low_bound}–{shown_high}"
    elif project == "firsts":
        shown_high = min(high_bound, low_bound + len(score_ls_filtered) - 1)
        section_title = "第一名成绩"
        range_label = f"榜一 {low_bound}–{shown_high}"
    elif project == "prlist":
        section_title, range_label = "上传成绩", "近 24 小时"
    elif project == "relist":
        section_title, range_label = "上传成绩", "近 24 小时 · 含未通过"
    elif project == "map_scores":
        section_title = "谱面成绩"
        range_label = f"搜索结果 · {len(score_ls_filtered)} 个难度"
    else:
        section_title, range_label = "新增最佳成绩", f"近 {day} 日"
    payload = {
        "mode": mode,
        "section_title": section_title,
        "range_label": range_label,
        "generated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "user": {
            "id": info.id,
            "name": info.username,
            "avatar_data": avatar_data,
            "country": info.country_code,
            "support_level": info.support_level,
            "team": ({**info.team.model_dump(), "flag_data": team_data} if info.team else None),
            "statistics": info.statistics.model_dump() if info.statistics else {},
        },
        "plays": plays,
    }
    return await render_bp_svg(payload)
