import asyncio
from io import BytesIO
from pathlib import Path

from rosu_pp_py import Beatmap as RosuBeatmap, GameMode, Performance

from ..api import get_beatmapsets_info, osu_api
from ..beatmap_stats_moder import with_mods
from ..file import ensure_osu_file
from ..performance import (
    PerformanceReport,
    PerformanceScenario,
    calculate_performance_report,
    format_scenario,
)
from ..schema import Beatmap
from ..schema.score import Mod
from ..utils import GM, normalize_map_mode
from .map_render import (
    duration_text,
    file_data_uri,
    cached_avatar_data_uri,
    beatmap_background_data_uri,
)
from .map_svg import render_map_svg


TEMPLATE_PATH = Path(__file__).parent / "map_templates"
MOD_PATH = Path(__file__).parent.parent / "osufile" / "mods"
GAME_MODES = (GameMode.Osu, GameMode.Taiko, GameMode.Catch, GameMode.Mania)
OBJECT_LABELS = {
    0: ("圆圈", "滑条", "转盘"),
    1: ("音符", "滚奏", "转盘"),
    2: ("水果", "果串", "香蕉"),
    3: ("单键", "长键", "其他"),
}
GENRE_NAMES = {
    0: "未分类",
    1: "未分类",
    2: "游戏音乐",
    3: "动漫",
    4: "摇滚",
    5: "流行音乐",
    6: "其他",
    7: "新奇音乐",
    9: "嘻哈",
    10: "电子音乐",
    11: "金属",
    12: "古典",
    13: "民谣",
    14: "爵士",
}
LANGUAGE_NAMES = {
    0: "其他",
    1: "其他",
    2: "英语",
    3: "日语",
    4: "中文",
    5: "纯音乐",
    6: "韩语",
    7: "法语",
    8: "德语",
    9: "瑞典语",
    10: "西班牙语",
    11: "意大利语",
    12: "俄语",
    13: "波兰语",
    14: "其他",
}


def _mode_stats(original: Beatmap, current: Beatmap) -> list[dict[str, str | float]]:
    od = {"key": "OD", "name": "判定难度", "before": original.accuracy, "after": current.accuracy}
    hp = {"key": "HP", "name": "体力消耗", "before": original.drain, "after": current.drain}
    if current.mode_int == 1:
        return [od, hp]
    if current.mode_int == 3:
        keys = {"key": "KEYS", "name": "键位数", "before": original.cs, "after": current.cs}
        return [keys, od, hp]
    return [
        {"key": "CS", "name": "圆圈大小", "before": original.cs, "after": current.cs},
        {"key": "AR", "name": "接近速度", "before": original.ar, "after": current.ar},
        od,
        hp,
    ]


def _ruleset_map(path: Path, mode: int, mods: list[str]) -> RosuBeatmap:
    beatmap = RosuBeatmap(path=str(path.absolute()))
    target = GAME_MODES[mode]
    if beatmap.mode != target:
        beatmap.convert(target, mods)
    return beatmap


def _apply_ruleset_metadata(mapinfo: Beatmap, ruleset_map: RosuBeatmap, mode: int, mods: list[str]) -> Beatmap:
    mapinfo.mode_int = mode
    mapinfo.mode = GM[mode]
    mapinfo.cs = ruleset_map.cs
    mapinfo.ar = ruleset_map.ar
    mapinfo.accuracy = ruleset_map.od
    mapinfo.drain = ruleset_map.hp
    mapinfo.bpm = ruleset_map.bpm

    if mode == 3:
        forced_keys = next((int(mod[0]) for mod in mods if len(mod) == 2 and mod[1] == "K" and mod[0].isdigit()), None)
        if forced_keys is not None:
            mapinfo.cs = forced_keys
        mapinfo.count_circles = ruleset_map.n_circles
        mapinfo.count_sliders = ruleset_map.n_holds
        mapinfo.count_spinners = max(ruleset_map.n_objects - ruleset_map.n_circles - ruleset_map.n_holds, 0)
    else:
        mapinfo.count_circles = ruleset_map.n_circles
        mapinfo.count_sliders = ruleset_map.n_sliders
        mapinfo.count_spinners = ruleset_map.n_spinners
    return mapinfo


def _scenario_payload(report: PerformanceReport) -> dict:
    return {
        "label": format_scenario(report.scenario, report.requested.max_combo),
        "pp": report.requested.pp,
        "stars": report.requested.stars,
        "accuracy": report.scenario.accuracy,
        "points": [
            {
                "accuracy": point.accuracy,
                "pp": point.pp,
                "selected": abs(point.accuracy - report.scenario.accuracy) < 0.0001,
            }
            for point in report.points
        ],
    }


def _performance_payload(
    original_map: RosuBeatmap,
    current_map: RosuBeatmap,
    mods: list[str],
) -> tuple[dict, dict]:
    points = []
    ss_attributes = None
    for accuracy in (100.0, 99.0, 98.0, 95.0, 90.0):
        attributes = Performance(mods=mods, accuracy=accuracy).calculate(current_map)
        if ss_attributes is None:
            ss_attributes = attributes
        points.append({"accuracy": accuracy, "pp": attributes.pp, "selected": accuracy == 100.0})
    assert ss_attributes is not None
    original_attributes = Performance(accuracy=100.0).calculate(original_map)
    components = {
        "aim": ss_attributes.pp_aim or 0.0,
        "speed": ss_attributes.pp_speed or 0.0,
        "accuracy": ss_attributes.pp_accuracy or 0.0,
        "difficulty": ss_attributes.pp_difficulty or 0.0,
        "catch": ss_attributes.pp if ss_attributes.difficulty.mode == GameMode.Catch else 0.0,
    }
    summary = {
        "stars": ss_attributes.difficulty.stars,
        "original_stars": original_attributes.difficulty.stars,
        "ss_pp": ss_attributes.pp,
        "max_combo": ss_attributes.difficulty.max_combo,
        "pp_matrix": points,
    }
    return summary, components


def _named_metadata(raw_set: dict, key: str, fallback: dict[int, str]) -> str:
    value = raw_set.get(key)
    if isinstance(value, dict):
        return str(value.get("name") or value.get("name_unicode") or fallback.get(int(value.get("id") or 0), "其他"))
    return fallback.get(int(raw_set.get(f"{key}_id") or 0), "其他")


def _nominations_text(raw_set: dict) -> str:
    nominations = raw_set.get("current_nominations") or []
    related_users = {
        user.get("id"): user.get("username")
        for user in raw_set.get("related_users") or []
        if user.get("id") is not None and user.get("username")
    }
    names = []
    for nomination in nominations:
        user = nomination.get("user") or {}
        name = user.get("username") or nomination.get("username") or related_users.get(nomination.get("user_id"))
        if name and name not in names:
            names.append(str(name))
    if names:
        return " / ".join(names[:3])
    summary = raw_set.get("nominations_summary") or {}
    current = summary.get("current")
    required = summary.get("required")
    if current is not None and required is not None:
        return f"{current} / {required} 已提名"
    return "暂无"


def _rating_payload(raw_set: dict) -> tuple[float | None, int, list[int]]:
    distribution = [int(value or 0) for value in (raw_set.get("ratings") or [])]
    votes = sum(distribution)
    if not votes:
        return None, 0, distribution
    rating = sum(index * count for index, count in enumerate(distribution)) / votes
    return rating, votes, distribution


async def draw_map_info(
    mapid: int,
    mods: list[str],
    target_mode: int | None = None,
    *,
    scenario: PerformanceScenario | None = None,
) -> BytesIO:
    raw_map = await osu_api("map", map_id=mapid)
    api_map = Beatmap(**raw_map)
    beatmapset = api_map.beatmapset
    if beatmapset is None:
        raise ValueError("谱面信息缺少谱面组数据")

    mod_names = [name.upper() for name in mods]
    mode = int(normalize_map_mode(target_mode, api_map.mode_int)) if target_mode is not None else api_map.mode_int
    beatmapset_task = asyncio.create_task(get_beatmapsets_info(api_map.beatmapset_id))
    try:
        osu_file = await ensure_osu_file(api_map.beatmapset_id, mapid, api_map.checksum)
    except Exception:
        beatmapset_task.cancel()
        raise
    try:
        full_beatmapset = await beatmapset_task
    except Exception:
        full_beatmapset = None

    original_ruleset = _ruleset_map(osu_file, mode, [])
    current_ruleset = _ruleset_map(osu_file, mode, mod_names)
    original = _apply_ruleset_metadata(api_map.model_copy(deep=True), original_ruleset, mode, [])
    current = _apply_ruleset_metadata(
        api_map.model_copy(deep=True),
        current_ruleset,
        mode,
        mod_names,
    )
    current = with_mods(current, None, [Mod(acronym=name) for name in mod_names])

    performance, pp_components = _performance_payload(original_ruleset, current_ruleset, mod_names)
    raw_set = raw_map.get("beatmapset") or {}
    rating, rating_votes, rating_distribution = _rating_payload(raw_set)
    failtimes = raw_map.get("failtimes") or {}
    if full_beatmapset is not None:
        difficulties = [
            {
                "id": item.id,
                "version": item.version,
                "stars": performance["stars"] if item.id == current.id else item.difficulty_rating,
                "current": item.id == current.id,
            }
            for item in full_beatmapset.beatmaps
        ]
    else:
        raw_difficulties = raw_set.get("beatmaps") or []
        difficulties = [
            {
                "id": item.get("id"),
                "version": item.get("version") or "Difficulty",
                "stars": (
                    performance["stars"] if item.get("id") == current.id else float(item.get("difficulty_rating") or 0)
                ),
                "current": item.get("id") == current.id,
            }
            for item in raw_difficulties
        ]
    if not difficulties:
        difficulties = [
            {
                "id": current.id,
                "version": current.version,
                "stars": performance["stars"],
                "current": True,
            }
        ]
    resource_tasks = [
        beatmap_background_data_uri(
            original.id,
            original.beatmapset_id,
            f"https://assets.ppy.sh/beatmaps/{original.beatmapset_id}/covers/cover@2x.jpg",
        ),
        cached_avatar_data_uri(original.user_id),
    ]
    if scenario is not None:
        resource_tasks.append(
            asyncio.to_thread(
                calculate_performance_report,
                osu_file,
                mode,
                mod_names,
                scenario,
            )
        )
    resources = await asyncio.gather(*resource_tasks)
    cover, avatar = resources[:2]
    scenario_report = resources[2] if scenario is not None else None
    mod_images = {
        name: file_data_uri(MOD_PATH / f"{name}.png", "image/png")
        for name in mod_names
        if (MOD_PATH / f"{name}.png").exists()
    }

    payload = {
        "mod_images": mod_images,
        "set": {
            "id": beatmapset.id,
            "title": beatmapset.title,
            "title_unicode": beatmapset.title_unicode,
            "artist": beatmapset.artist,
            "artist_unicode": beatmapset.artist_unicode,
            "creator": beatmapset.creator,
            "user_id": beatmapset.user_id,
            "source": beatmapset.source,
            "status": original.status,
            "ranked_date": (beatmapset.ranked_date or "")[:10].replace("-", "."),
            "favourites": beatmapset.favourite_count,
            "tags": beatmapset.tags.split() if beatmapset.tags else [],
            "genre": _named_metadata(raw_set, "genre", GENRE_NAMES),
            "language": _named_metadata(raw_set, "language", LANGUAGE_NAMES),
            "nominations": _nominations_text(full_beatmapset.model_dump() if full_beatmapset is not None else raw_set),
            "cover": cover,
            "avatar": avatar,
        },
        "map": {
            "id": current.id,
            "version": current.version,
            "mode_int": current.mode_int,
            "stars": performance["stars"],
            "original_stars": performance["original_stars"],
            "ss_pp": performance["ss_pp"],
            "pp_components": pp_components,
            "pp_matrix": performance["pp_matrix"],
            "bpm": current.bpm or 0,
            "original_bpm": original.bpm or 0,
            "duration": duration_text(current.total_length),
            "drain_duration": duration_text(current.hit_length),
            "max_combo": performance["max_combo"],
            "objects": current.count_circles + current.count_sliders + current.count_spinners,
            "circles": current.count_circles,
            "sliders": current.count_sliders,
            "spinners": current.count_spinners,
            "plays": current.playcount,
            "passes": current.passcount,
            "mods": [name for name in mod_names if name in mod_images],
            "stats": _mode_stats(original, current),
            "object_labels": OBJECT_LABELS[mode],
            "rating": rating,
            "rating_votes": rating_votes,
            "rating_distribution": rating_distribution,
            "fail_points": failtimes.get("fail") or [],
        },
        "difficulties": difficulties,
        "scenario": _scenario_payload(scenario_report) if scenario_report is not None else None,
    }
    return await render_map_svg(payload)
