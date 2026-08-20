import asyncio
from io import BytesIO
from pathlib import Path

from rosu_pp_py import Beatmap as RosuBeatmap, GameMode

from ..api import osu_api
from ..beatmap_stats_moder import with_mods
from ..file import ensure_osu_file
from ..performance import (
    PerformanceReport,
    PerformanceScenario,
    calculate_performance_report,
    format_scenario,
)
from ..pp import get_ss_pp
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
    osu_file = await ensure_osu_file(api_map.beatmapset_id, mapid, api_map.checksum)

    original = _apply_ruleset_metadata(api_map.model_copy(deep=True), _ruleset_map(osu_file, mode, []), mode, [])
    current = _apply_ruleset_metadata(
        api_map.model_copy(deep=True),
        _ruleset_map(osu_file, mode, mod_names),
        mode,
        mod_names,
    )
    current = with_mods(current, None, [Mod(acronym=name) for name in mod_names])

    ss_result = get_ss_pp(str(osu_file.absolute()), mode, mod_names)
    original_ss_result = get_ss_pp(str(osu_file.absolute()), mode, [])
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
            "cover": cover,
            "avatar": avatar,
        },
        "map": {
            "id": current.id,
            "version": current.version,
            "mode_int": current.mode_int,
            "stars": ss_result.stars,
            "original_stars": original_ss_result.stars,
            "ss_pp": ss_result.pp,
            "bpm": current.bpm or 0,
            "original_bpm": original.bpm or 0,
            "duration": duration_text(current.total_length),
            "max_combo": ss_result.max_combo,
            "objects": current.count_circles + current.count_sliders + current.count_spinners,
            "circles": current.count_circles,
            "sliders": current.count_sliders,
            "spinners": current.count_spinners,
            "plays": current.playcount,
            "passes": current.passcount,
            "mods": [name for name in mod_names if name in mod_images],
            "stats": _mode_stats(original, current),
            "object_labels": OBJECT_LABELS[mode],
        },
        "scenario": _scenario_payload(scenario_report) if scenario_report is not None else None,
    }
    return await render_map_svg(payload)
