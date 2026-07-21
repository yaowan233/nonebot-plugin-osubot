import asyncio
import base64
from io import BytesIO
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import jinja2
from osu_tools import OsuCalculator
from nonebot_plugin_htmlrender import get_new_page

from ..info import get_bg
from ..utils import FGM, NGM, normalize_map_mode
from ..mods import get_mods_list
from ..exceptions import NetworkError
from ..schema.user import UnifiedUser
from ..schema import Beatmap, NewScore
from ..beatmap_stats_moder import with_mods
from ..pp import cal_pp, get_if_pp_ss_pp, get_pp_components
from ..schema.score import Mod, UnifiedScore, NewStatistics
from ..api import osu_api, get_user_scores, get_user_info_data, get_ppysb_map_scores
from ..file import map_path, download_osu, user_cache_path, team_cache_path, get_projectimg
from .utils import (
    is_close,
    calc_songlen,
    open_user_icon,
    filter_scores_with_regex,
)
from .static import (
    Image,
    osufile,
)


async def draw_score(
    project: str,
    uid: int,
    is_lazer: bool,
    mode: str,
    mods: Optional[list[str]],
    search_condition: list,
    source: str = "osu",
    best: int = 1,
    *,
    return_context: bool = False,
) -> BytesIO | tuple[BytesIO, int, int]:
    task1 = asyncio.create_task(get_user_info_data(uid, mode, source))
    if project == "bp":
        scores = await get_user_scores(uid, mode, "best", source=source, legacy_only=not is_lazer, limit=best)

    else:
        if project == "pr":
            scores = await get_user_scores(
                uid,
                mode,
                "recent",
                source=source,
                legacy_only=not is_lazer,
                include_failed=False,
                limit=best,
            )
        else:
            scores = await get_user_scores(uid, mode, "recent", source=source, legacy_only=not is_lazer, limit=best)
    if not scores:
        raise NetworkError("未查询到游玩记录")
    if project in ("recent", "pr"):
        if len(scores) < best:
            raise NetworkError("未查询到游玩记录")
        score = scores[best - 1]
    elif project == "bp":
        if search_condition:
            scores = filter_scores_with_regex(scores, search_condition)
        mods_ls = get_mods_list(scores, mods)
        if len(mods_ls) < best:
            raise NetworkError("未查询到游玩记录")
        score = scores[mods_ls[best - 1]]
    else:
        raise Exception("Project Error")
    # 从官网获取信息
    path = map_path / str(score.beatmap.set_id)
    path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{score.beatmap.id}.osu"
    task2 = asyncio.create_task(osu_api("map", map_id=score.beatmap.id))
    if not osu.exists():
        await download_osu(score.beatmap.set_id, score.beatmap.id)
    info = await task1
    user_path = user_cache_path / str(info.id)
    user_path.mkdir(parents=True, exist_ok=True)
    map_json = await task2
    # 判断是否开启lazer模式
    if source == "osu":
        score = cal_score_info(is_lazer, score, source)
    image = await draw_score_pic(score, info, map_json, "", source)
    if return_context:
        return image, score.beatmap.id, score.beatmap.set_id
    return image


async def get_score_data(
    uid: int,
    is_lazer: bool,
    mode: Optional[str],
    mods: Optional[list[str]],
    mapid: int = 0,
    source: str = "osu",
) -> BytesIO:
    grank = ""
    map_json = await osu_api("map", map_id=mapid)
    native_mode = int(map_json["mode_int"])
    mode = NGM[normalize_map_mode(FGM[mode], native_mode, source)]
    task = asyncio.create_task(get_user_info_data(uid, mode, source))
    if source == "osu":
        if mods:
            score_json = await osu_api("score", uid, mode, mapid, legacy_only=int(not is_lazer))
            score_ls = [NewScore(**i) for i in score_json["scores"]]
        else:
            score_json = await osu_api("best_score", uid, mode, mapid, legacy_only=int(not is_lazer))
            grank = score_json.get("position", "")
            score_ls = [NewScore(**score_json["score"])]
        score_ls = [
            UnifiedScore(
                mods=i.mods,
                ruleset_id=i.ruleset_id,
                rank=i.rank,
                accuracy=i.accuracy * 100,
                total_score=i.total_score,
                ended_at=datetime.strptime(i.ended_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8),
                max_combo=i.max_combo,
                statistics=i.statistics,
                legacy_total_score=i.legacy_total_score,
                passed=i.passed,
            )
            for i in score_ls
        ]
    else:
        score_ls = await get_ppysb_map_scores(map_json["checksum"], uid, mode)
    if not score_ls:
        raise NetworkError("未查询到游玩记录")
    if mods:
        for i in score_ls:
            if mods == ["NM"] and not i.mods:
                score = i
                break
            if i.mods == [Mod(acronym=j) for j in mods]:
                score = i
                break
        else:
            score_ls.sort(key=lambda x: x.total_score, reverse=True)
            for i in score_ls:
                if set(mods).issubset(mod.acronym for mod in i.mods):
                    score = i
                    break
            else:
                raise NetworkError(f"未找到开启 {'|'.join(mods)} Mods的成绩")
    else:
        score_ls.sort(key=lambda x: x.total_score, reverse=True)
        score = score_ls[0]
    path = map_path / str(map_json["beatmapset_id"])
    path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(map_json["beatmapset_id"], mapid)
    info = await task
    user_path = user_cache_path / str(info.id)
    user_path.mkdir(parents=True, exist_ok=True)
    # 判断是否开启lazer模式
    if source == "osu":
        score = cal_score_info(is_lazer, score, source)
    return await draw_score_pic(score, info, map_json, grank, source)


async def draw_score_pic(score_info: UnifiedScore, info: UnifiedUser, map_json, grank, source) -> BytesIO:
    if score_info.mods:
        has_nc = any(m.acronym == "NC" for m in score_info.mods)
        if has_nc:
            score_info.mods = [m for m in score_info.mods if m.acronym != "DT"]
    mapinfo = Beatmap(**map_json)
    original_mapinfo = mapinfo.model_copy(deep=True)
    mapinfo = with_mods(mapinfo, score_info, score_info.mods)
    # mania 转谱的键位数沿用原绘图逻辑计算。
    if score_info.ruleset_id == 3 and mapinfo.mode == "osu":
        temp_accuracy = mapinfo.accuracy
        total_objects = mapinfo.count_circles + mapinfo.count_sliders + mapinfo.count_spinners
        convert = (mapinfo.count_sliders + mapinfo.count_spinners) / total_objects if total_objects else 0
        convert_od = round(temp_accuracy)
        if convert < 0.20 or (convert < 0.30 or round(mapinfo.cs) >= 5) and convert_od > 5:
            mapinfo.cs = 7.0
        elif (convert < 0.30 or round(mapinfo.cs) >= 5) and convert_od <= 5:
            mapinfo.cs = 6.0
        elif convert > 0.60 and convert_od > 4:
            mapinfo.cs = 5.0
        elif convert > 0.60 and convert_od <= 4:
            mapinfo.cs = 4.0
        else:
            temp_accuracy += 1
            mapinfo.cs = max(4.0, min(temp_accuracy, 7.0))
        original_mapinfo.cs = mapinfo.cs
    path = map_path / str(mapinfo.beatmapset_id)
    path.mkdir(parents=True, exist_ok=True)
    # pp
    osu = path / f"{mapinfo.id}.osu"
    pp_info = cal_pp(score_info, str(osu.absolute()), source)
    if_pp, ss_pp = get_if_pp_ss_pp(score_info, str(osu.absolute()), source)
    display_stars = pp_info.stars
    display_pp = score_info.pp if source == "ppysb" and score_info.pp is not None else pp_info.pp
    return await render_score_template(
        score_info,
        info,
        mapinfo,
        original_mapinfo,
        pp_info,
        display_pp,
        display_stars,
        if_pp,
        ss_pp,
        grank,
        str(osu.absolute()),
        source,
    )


def _format_pp(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number >= 1000:
        return f"{number:,.0f}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def _format_stat(value) -> str:
    return f"{int(value or 0):,}"


def _image_data_uri(image: Image.Image, image_format: str = "PNG") -> str:
    output = BytesIO()
    frame = image.convert("RGBA" if image_format == "PNG" else "RGB")
    frame.save(output, image_format, optimize=True)
    return f"data:image/{image_format.lower()};base64,{base64.b64encode(output.getvalue()).decode()}"


async def _owner_avatar_data(owner_id: int) -> str:
    owner_path = user_cache_path / str(owner_id)
    owner_path.mkdir(parents=True, exist_ok=True)
    avatar_path = owner_path / "mapper_avatar.png"
    try:
        if not avatar_path.exists():
            avatar_bytes = await get_projectimg(f"https://a.ppy.sh/{owner_id}")
            with Image.open(avatar_bytes) as avatar:
                avatar.convert("RGBA").save(avatar_path, "PNG")
        with Image.open(avatar_path) as avatar:
            return _image_data_uri(avatar)
    except Exception:
        placeholder = Image.new("RGBA", (32, 32), (40, 55, 68, 255))
        return _image_data_uri(placeholder)


async def _team_icon_data(info: UnifiedUser) -> str | None:
    if not info.team or not info.team.flag_url:
        return None
    icon_path = team_cache_path / f"{info.team.id}.png"
    try:
        if not icon_path.exists():
            icon_bytes = await get_projectimg(info.team.flag_url)
            with Image.open(icon_bytes) as icon:
                icon.convert("RGBA").save(icon_path, "PNG")
        with Image.open(icon_path) as icon:
            return _image_data_uri(icon)
    except Exception:
        return None


async def render_score_template(
    score_info: UnifiedScore,
    info: UnifiedUser,
    mapinfo: Beatmap,
    original_mapinfo: Beatmap,
    pp_info,
    display_pp: float,
    display_stars: float,
    if_pp: str,
    ss_pp: str,
    grank,
    osu_path: str,
    source: str,
) -> BytesIO:
    mode = score_info.ruleset_id % 4
    mode_names = ["标准模式", "太鼓模式", "接水果模式", "键盘模式"]
    mode_codes = ["OSU", "TAIKO", "CATCH", "MANIA"]
    stats = score_info.statistics

    if mode == 0:
        judgements = [
            ("GREAT / 300", stats.great),
            ("OK / 100", stats.ok),
            ("MEH / 50", stats.meh),
            ("MISS / 失误", stats.miss),
        ]
        judge_cols = 2
        ratio = None
    elif mode == 1:
        judgements = [("GREAT / 良", stats.great), ("OK / 可", stats.ok), ("MISS / 失误", stats.miss)]
        judge_cols = 3
        ratio = None
    elif mode == 2:
        judgements = [
            ("FRUIT / 水果", stats.great),
            ("LARGE DROPLET", stats.large_tick_hit),
            ("SMALL DROPLET", stats.small_tick_miss),
            ("MISS / 失误", stats.miss),
        ]
        judge_cols = 2
        ratio = None
    else:
        judgements = [
            ("MAX / 彩 300", stats.perfect),
            ("300", stats.great),
            ("200", stats.good),
            ("100", stats.ok),
            ("50", stats.meh),
            ("MISS", stats.miss),
        ]
        judge_cols = 3
        ratio = f"{stats.perfect / stats.great:.1f} : 1" if stats.great else "∞ : 1"

    od = ("OD", original_mapinfo.accuracy, mapinfo.accuracy)
    hp = ("HP", original_mapinfo.drain, mapinfo.drain)
    if mode == 1:
        dimension_values = [od, hp]
    elif mode == 3:
        dimension_values = [("KEYS", original_mapinfo.cs, mapinfo.cs), od, hp]
    else:
        dimension_values = [
            ("CS", original_mapinfo.cs, mapinfo.cs),
            ("AR", original_mapinfo.ar, mapinfo.ar),
            od,
            hp,
        ]
    dimension_max = 11 if any(current > 10 for _, _, current in dimension_values) else 10
    dimensions = []
    for name, original, current in dimension_values:
        changed = not is_close(original, current)
        dimensions.append(
            {
                "name": name,
                "original": f"{original:.0f}" if name == "KEYS" else f"{original:.1f}",
                "current": f"{current:.0f}" if name == "KEYS" else f"{current:.1f}",
                "changed": changed,
                "original_pos": min(100, max(0, original / dimension_max * 100)),
                "current_pos": min(100, max(0, current / dimension_max * 100)),
            }
        )

    accuracy_pp = {}
    target_accuracies = (96, 98) if mode in {0, 1, 3} else ()
    try:
        calculator = OsuCalculator()
        for target_accuracy in target_accuracies:
            accuracy_pp[target_accuracy] = calculator.calculate(
                osu_path,
                mode,
                score_info.mods,
                target_accuracy,
            ).pp
    except Exception:
        accuracy_pp = dict.fromkeys(target_accuracies, "nan")
    try:
        mode_pp = get_pp_components(score_info, osu_path, source)
    except Exception:
        mode_pp = {}

    if mode == 0:
        pp_components = [
            ("AIM", pp_info.pp_aim),
            ("SPEED", pp_info.pp_speed),
            ("ACC", pp_info.pp_acc),
        ]
        pp_targets = [
            ("96% ACC", accuracy_pp[96]),
            ("98% ACC", accuracy_pp[98]),
            ("IF FC", if_pp),
            ("SS PP", ss_pp),
        ]
        pp_items = []
    elif mode == 1:
        pp_components = [
            ("难度", mode_pp.get("difficulty", 0)),
            ("准确", mode_pp.get("accuracy", 0)),
        ]
        pp_targets = [
            ("96% ACC", accuracy_pp[96]),
            ("98% ACC", accuracy_pp[98]),
            ("SS PP", ss_pp),
        ]
        pp_items = []
    elif mode == 2:
        pp_components = [("PP 值", display_pp)]
        pp_targets = [("IF FC", if_pp), ("SS PP", ss_pp)]
        pp_items = []
    elif mode == 3:
        pp_components = [("PP 值", display_pp)]
        pp_targets = [
            ("96% ACC", accuracy_pp[96]),
            ("98% ACC", accuracy_pp[98]),
            ("SS PP", ss_pp),
        ]
        pp_items = []

    owners = list(mapinfo.owners or [])
    if not owners:
        owners = [
            {
                "id": mapinfo.beatmapset.user_id,
                "username": mapinfo.beatmapset.creator,
            }
        ]
    owner_pairs = []
    for owner in owners[:20]:
        owner_id = owner.id if hasattr(owner, "id") else owner["id"]
        username = owner.username if hasattr(owner, "username") else owner["username"]
        owner_pairs.append((owner_id, username))
    owner_avatars = await asyncio.gather(*(_owner_avatar_data(owner_id) for owner_id, _ in owner_pairs))
    owner_data = [
        {"id": owner_id, "username": username, "avatar": avatar}
        for (owner_id, username), avatar in zip(owner_pairs, owner_avatars)
    ]

    mod_data = []
    for mod in score_info.mods:
        icon = osufile / "mods" / f"{mod.acronym}.png"
        if icon.exists():
            mod_data.append({"name": mod.acronym, "icon": icon.as_uri()})

    rank_image = osufile / "ranking" / f"legacy-ranking-{score_info.rank}@2x.png"
    if not rank_image.exists():
        rank_image = osufile / "ranking" / f"ranking-{score_info.rank}.png"

    try:
        cover_image = await get_bg(mapinfo.id, mapinfo.beatmapset_id)
        cover = _image_data_uri(cover_image, "JPEG")
        cover_image.close()
    except Exception:
        cover = _image_data_uri(Image.new("RGB", (640, 360), (9, 18, 29)), "JPEG")
    try:
        player_image = await open_user_icon(info, source)
        player_avatar = _image_data_uri(player_image)
        player_image.close()
    except Exception:
        player_avatar = _image_data_uri(Image.new("RGBA", (128, 128), (30, 45, 58, 255)))
    total_objects = mapinfo.count_circles + mapinfo.count_sliders + mapinfo.count_spinners
    combo = (
        f"{score_info.max_combo:,} / {pp_info.max_combo:,}x"
        if mode in {0, 1, 2} and pp_info.max_combo
        else f"{score_info.max_combo:,}x"
    )
    judgement_total = sum(int(value or 0) for _, value in judgements)
    miss_count = int(stats.miss or 0)
    combo_completion = score_info.max_combo / pp_info.max_combo * 100 if pp_info.max_combo else 0
    combo_is_full = bool(pp_info.max_combo and score_info.max_combo >= pp_info.max_combo)
    team = info.team.model_dump() if info.team else None
    if team is not None:
        team["icon"] = await _team_icon_data(info)
    profile_third_label = "成绩排名" if grank else "玩家等级"
    profile_third_value = (
        f"#{grank}"
        if grank
        else f"Lv.{info.statistics.level.current}"
        if info.statistics and info.statistics.level
        else "—"
    )
    data = {
        "mode_name": mode_names[mode],
        "mode_code": mode_codes[mode],
        "eyebrow": "COLLABORATIVE BEATMAP" if len(owner_data) > 1 else "BEATMAP PERFORMANCE",
        "ended_at": score_info.ended_at.strftime("%Y.%m.%d %H:%M:%S"),
        "status": mapinfo.status.upper(),
        "title": mapinfo.beatmapset.title,
        "title_class": (
            "title-short"
            if len(mapinfo.beatmapset.title) <= 14
            else "title-medium"
            if len(mapinfo.beatmapset.title) <= 28
            else "title-long"
        ),
        "artist": mapinfo.beatmapset.artist,
        "version": mapinfo.version,
        "cover": cover,
        "bpm": f"{mapinfo.bpm:g}" if mapinfo.bpm is not None else "--",
        "length": calc_songlen(mapinfo.total_length),
        "objects": f"{total_objects:,}",
        "map_id": mapinfo.id,
        "set_id": mapinfo.beatmapset_id,
        "avatar": player_avatar,
        "username": info.username,
        "support_level": max(0, min(5, int(info.support_level or 0))),
        "user_id": info.id,
        "country": info.country_code,
        "country_rank": info.statistics.country_rank if info.statistics else None,
        "global_rank": info.statistics.global_rank if info.statistics else None,
        "team": team,
        "owners": owner_data,
        "mods": mod_data,
        "score": f"{(score_info.legacy_total_score or score_info.total_score):,}",
        "pp": _format_pp(display_pp),
        "accuracy": f"{score_info.accuracy:.4f}" if mode == 3 else f"{score_info.accuracy:.2f}",
        "combo": combo,
        "combo_is_full": combo_is_full,
        "stars": f"{display_stars:.2f}",
        "rank_image": rank_image.as_uri(),
        "score_rank": grank,
        "profile_third_label": profile_third_label,
        "profile_third_value": profile_third_value,
        "judgement_total": f"{judgement_total:,}",
        "miss_rate": f"{miss_count / judgement_total * 100:.2f}%" if judgement_total else "0.00%",
        "combo_completion": f"{combo_completion:.1f}%",
        "ratio": ratio,
        "judge_cols": judge_cols,
        "judgements": [
            {"label": label, "value": int(value or 0), "display": _format_stat(value)} for label, value in judgements
        ],
        "dimension_max": dimension_max,
        "dimensions": dimensions,
        "pp_components": [{"label": label, "value": _format_pp(value)} for label, value in pp_components],
        "pp_has_breakdown": mode in {0, 1},
        "total_pp": _format_pp(display_pp),
        "pp_target_title": "满连推演" if mode == 2 else "准确率推演",
        "pp_targets": [{"label": label, "value": _format_pp(value)} for label, value in pp_targets],
        "pp_items": [{"label": label, "value": _format_pp(value)} for label, value in pp_items],
    }

    template_path = Path(__file__).parent / "score_templates"
    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_path), enable_async=True)  # noqa: S701
    template = template_env.get_template("index.html")
    async with get_new_page(2) as page:
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.goto((template_path / "index.html").as_uri(), wait_until="load")
        await page.set_content(await template.render_async(d=data), wait_until="domcontentloaded")
        await page.evaluate("colourStarBadge()")
        await page.evaluate(
            "Promise.race([Promise.all([document.fonts.ready, "
            "...Array.from(document.images, image => image.decode().catch(() => {}))]), "
            "new Promise(resolve => setTimeout(resolve, 8000))])"
        )
        # 字体就绪后再跑一次自适应，确保标题/艺人名按真实字宽收缩
        await page.evaluate("fitBeatmapTitle();fitArtistName()")
        elem = await page.query_selector("#score")
        assert elem
        return BytesIO(await elem.screenshot(type="jpeg", quality=92))


def cal_legacy_acc(statistics: NewStatistics) -> float:
    statistics.great = statistics.great or 0
    statistics.good = statistics.good or 0
    statistics.ok = statistics.ok or 0
    statistics.meh = statistics.meh or 0
    statistics.perfect = statistics.perfect or 0
    statistics.miss = statistics.miss or 0
    num = statistics.great + statistics.good + statistics.ok + statistics.meh + statistics.perfect + statistics.miss
    if num == 0:
        return 1
    return (
        (
            statistics.perfect * 300
            + statistics.great * 300
            + statistics.good * 200
            + statistics.ok * 100
            + statistics.meh * 50
        )
        / (num * 300)
        * 100
    )


def cal_legacy_rank(score_info: UnifiedScore, is_hidden: bool):
    if not score_info.passed:
        return "F"
    great = score_info.statistics.great or 0
    miss = score_info.statistics.miss or 0
    meh = score_info.statistics.meh or 0
    ok = score_info.statistics.ok or 0

    if score_info.ruleset_id in {0, 4, 8}:
        max_combo = great + ok + meh + miss
    elif score_info.ruleset_id in {1, 5}:
        max_combo = great + ok + miss
    else:
        max_combo = score_info.max_combo

    max_combo_90 = max_combo * 0.9
    max_combo_80 = max_combo * 0.8
    max_combo_70 = max_combo * 0.7
    max_combo_60 = max_combo * 0.6
    max_combo_1_percent = max_combo * 0.01

    if score_info.accuracy == 1:
        return "XH" if is_hidden else "X"

    if score_info.ruleset_id == 3:
        if score_info.accuracy >= 95:
            return "SH" if is_hidden else "S"
        elif score_info.accuracy >= 90:
            return "A"
        elif score_info.accuracy >= 80:
            return "B"
        elif score_info.accuracy >= 70:
            return "C"
        else:
            return "D"

    elif score_info.ruleset_id in {2, 6}:
        if score_info.accuracy >= 98:
            return "SH" if is_hidden else "S"
        elif score_info.accuracy >= 94:
            return "A"
        elif score_info.accuracy >= 90:
            return "B"
        elif score_info.accuracy >= 85:
            return "C"
        else:
            return "D"

    elif score_info.ruleset_id in {1, 5}:
        if great >= max_combo_90 and miss == 0:
            return "SH" if is_hidden else "S"
        elif (great >= max_combo_80 and miss == 0) or great >= max_combo_90:
            return "A"
        elif (great >= max_combo_70 and miss == 0) or great >= max_combo_80:
            return "B"
        elif great >= max_combo_60:
            return "C"
        else:
            return "D"

    elif score_info.ruleset_id in {0, 4, 8}:
        if great >= max_combo_90 and meh <= max_combo_1_percent and miss == 0:
            return "SH" if is_hidden else "S"
        elif (great >= max_combo_80 and miss == 0) or great >= max_combo_90:
            return "A"
        elif (great >= max_combo_70 and miss == 0) or great >= max_combo_80:
            return "B"
        elif great >= max_combo_60:
            return "C"
        else:
            return "D"

    else:
        return "N/A"


def cal_score_info(is_lazer: bool, score_info: UnifiedScore, source: str = "osu") -> UnifiedScore:
    if score_info.ruleset_id == 3 and not is_lazer and source != "ppysb":
        score_info.accuracy = cal_legacy_acc(score_info.statistics)
    if not is_lazer and source != "ppysb":
        is_hidden = any(i in score_info.mods for i in (Mod(acronym="HD"), Mod(acronym="FL"), Mod(acronym="FI")))
        score_info.rank = cal_legacy_rank(score_info, is_hidden)
    return score_info
