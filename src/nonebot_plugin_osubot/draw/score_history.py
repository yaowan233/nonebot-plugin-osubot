import asyncio
from io import BytesIO
from datetime import datetime, timedelta

from ..pp import cal_stars
from ..utils import FGM, NGM, normalize_map_mode
from ..schema import Beatmap, NewScore
from ..exceptions import NetworkError
from ..mods import get_mods_list, get_speed_change_labels
from ..schema.score import UnifiedScore, NewStatistics, get_score_version
from ..api import osu_api, get_user_info_data, get_ppysb_map_scores
from ..file import ensure_osu_file, get_pfm_img, map_path
from .score import _player_avatar_data_uri, cal_score_info
from .score_history_svg import render_score_history_svg
from .static import ColorArr
from .svg_render import file_data_uri


def _to_datetime(value: str) -> datetime:
    return datetime.strptime(value.replace("Z", ""), "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8)


def _to_unified_score(score: NewScore) -> UnifiedScore:
    return UnifiedScore(
        mods=score.mods,
        ruleset_id=score.ruleset_id,
        rank=score.rank,
        accuracy=score.accuracy * 100,
        total_score=score.total_score,
        legacy_total_score=score.legacy_total_score,
        ended_at=_to_datetime(score.ended_at),
        max_combo=score.max_combo,
        statistics=score.statistics or NewStatistics(),
        passed=score.passed,
        pp=score.pp,
        score_version=get_score_version(score.legacy_score_id),
    )


def _judgements(score: UnifiedScore) -> list[tuple[str, int]]:
    stats = score.statistics
    mode = score.ruleset_id % 4
    if mode == 0:
        values = [("300", stats.great), ("100", stats.ok), ("50", stats.meh), ("MISS", stats.miss)]
    elif mode == 1:
        values = [("良", stats.great), ("可", stats.ok), ("MISS", stats.miss)]
    elif mode == 2:
        values = [
            ("水果", stats.great),
            ("大果粒", stats.large_tick_hit),
            ("小果粒漏", stats.small_tick_miss),
            ("MISS", stats.miss),
        ]
    else:
        values = [
            ("MAX", stats.perfect),
            ("300", stats.great),
            ("200", stats.good),
            ("100", stats.ok),
            ("50", stats.meh),
            ("MISS", stats.miss),
        ]
    return [(label, int(value or 0)) for label, value in values]


def _star_style(stars: float) -> tuple[str, str]:
    if stars < 0.1:
        color = "#aaaaaa"
    elif stars >= 9:
        color = "#000000"
    else:
        red, green, blue, _alpha = ColorArr[int(stars * 100)]
        color = f"#{red:02x}{green:02x}{blue:02x}"
    return color, "#101925" if stars < 6.5 else "#ffd966"


async def draw_score_history(
    uid: int,
    is_lazer: bool,
    mode: str,
    mods: list[str],
    map_id: int | str,
    source: str = "osu",
    score_range: str | None = None,
) -> BytesIO:
    map_id = int(map_id)
    map_json = await osu_api("map", map_id=map_id)
    native_mode = int(map_json["mode_int"])
    mode = NGM[normalize_map_mode(FGM[mode], native_mode, source)]
    info_task = asyncio.create_task(get_user_info_data(uid, mode, source))

    if source == "osu":
        response = await osu_api("score", uid, mode, map_id, legacy_only=int(not is_lazer))
        scores = [_to_unified_score(NewScore(**item)) for item in response.get("scores", [])]
    else:
        scores = await get_ppysb_map_scores(map_json["checksum"], uid, mode)

    if mods:
        if mods == ["NM"]:
            scores = [score for score in scores if not [mod for mod in score.mods if mod.acronym != "CL"]]
        else:
            scores = [scores[index] for index in get_mods_list(scores, mods)]
    if not scores:
        raise NetworkError("未查询到该谱面的游玩记录")

    scores.sort(key=lambda score: score.ended_at, reverse=True)
    total_count = len(scores)
    start, end = 1, total_count
    if score_range:
        start, end = (int(value) for value in score_range.split("-", 1))
        if start > total_count:
            raise NetworkError(f"该谱面只有 {total_count} 条可获取成绩")
        end = min(end, total_count)
        scores = scores[start - 1 : end]

    beatmap = Beatmap(**map_json)
    osu_path = map_path / str(beatmap.beatmapset_id) / f"{map_id}.osu"
    cover_path = map_path / str(beatmap.beatmapset_id) / "cover.jpg"
    await asyncio.gather(
        info_task,
        get_pfm_img(beatmap.beatmapset.covers.cover, cover_path),
        ensure_osu_file(beatmap.beatmapset_id, map_id, beatmap.checksum),
    )
    info = await info_task

    def build_play(offset: int, score: UnifiedScore) -> dict:
        score = cal_score_info(is_lazer, score, source)
        pp_value = float(score.pp or 0)
        stars = float(beatmap.difficulty_rating)
        try:
            stars = cal_stars(score, str(osu_path.absolute()), source)
        except Exception:
            pass
        speed_changes = get_speed_change_labels(score.mods)
        mod_names = [mod.acronym for mod in score.mods]
        if "NC" in mod_names and "DT" in mod_names:
            mod_names.remove("DT")
        star_color, star_text = _star_style(stars)
        return {
            "index": offset,
            "rank": score.rank,
            "passed": score.passed,
            "score": score.legacy_total_score or score.total_score,
            "pp": pp_value,
            "accuracy": score.accuracy,
            "combo": score.max_combo,
            "stars": stars,
            "star_color": star_color,
            "star_text": star_text,
            "mods": mod_names,
            "speed_changes": speed_changes,
            "judgements": _judgements(score),
            "date": score.ended_at.strftime("%Y.%m.%d %H:%M"),
            "score_version": score.score_version if source == "osu" else None,
        }

    plays = await asyncio.gather(
        *(asyncio.to_thread(build_play, offset, score) for offset, score in enumerate(scores, start=start))
    )

    best_key = max(range(len(plays)), key=lambda index: (plays[index]["score"], plays[index]["pp"]))
    plays[best_key]["best"] = True
    statistics = info.statistics.model_dump() if info.statistics else {}
    avatar_data = await _player_avatar_data_uri(info, source)
    map_star_color, map_star_text = _star_style(beatmap.difficulty_rating)
    data = {
        "source": "ppysb" if source == "ppysb" else "osu!",
        "score_version": "Stable" if not is_lazer else "Lazer + Stable",
        "mode": mode,
        "generated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "disclaimer": (
            "每种 Mod 组合显示 osu! API 当前保留的最佳成绩，不代表全部历史尝试"
            if source == "osu"
            else "显示 ppysb API 当前可返回的谱面成绩"
        ),
        "user": {
            "id": info.id,
            "name": info.username,
            "avatar_data": avatar_data,
            "country": info.country_code,
            "pp": statistics.get("pp", 0),
            "global_rank": statistics.get("global_rank"),
        },
        "map": {
            "id": beatmap.id,
            "set_id": beatmap.beatmapset_id,
            "title": beatmap.beatmapset.title,
            "artist": beatmap.beatmapset.artist,
            "version": beatmap.version,
            "creator": beatmap.beatmapset.creator,
            "stars": beatmap.difficulty_rating,
            "star_color": map_star_color,
            "star_text": map_star_text,
            "bpm": beatmap.bpm,
            "cover_data": file_data_uri(cover_path) if cover_path.exists() else None,
        },
        "plays": plays,
    }

    return await render_score_history_svg(data)
