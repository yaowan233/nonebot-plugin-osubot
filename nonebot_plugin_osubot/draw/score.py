import asyncio
from io import BytesIO
from typing import Optional
from datetime import datetime, timedelta

from PIL import ImageDraw, ImageFilter, ImageEnhance, ImageSequence, UnidentifiedImageError

from ..info import get_bg
from ..mods import get_mods_list
from ..exceptions import NetworkError
from ..schema.user import UnifiedUser
from ..schema import Beatmap, NewScore
from ..beatmap_stats_moder import with_mods
from ..pp import cal_pp, get_ss_pp, get_if_pp_ss_pp
from ..schema.score import Mod, UnifiedScore, NewStatistics
from ..api import osu_api, get_user_scores, get_user_info_data, get_ppysb_map_scores
from ..file import map_path, download_osu, get_projectimg, team_cache_path, user_cache_path
from .utils import (
    crop_bg,
    draw_acc,
    is_close,
    stars_diff,
    update_map,
    draw_fillet,
    update_icon,
    calc_songlen,
    get_modeimage,
    open_user_icon,
    filter_scores_with_regex,
    trim_text_with_ellipsis,
    draw_text_with_outline,
)
from .static import (
    Image,
    IconLs,
    Venera_60,
    Torus_Regular_15,
    Torus_Regular_20,
    Torus_Regular_25,
    Torus_Regular_50,
    Torus_Regular_60,
    Torus_SemiBold_15,
    Torus_SemiBold_20,
    Torus_SemiBold_25,
    Torus_SemiBold_30,
    osufile,
    extra_30,
    Stardiff,
    Stars,
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
) -> BytesIO:
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
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{score.beatmap.id}.osu"
    task2 = asyncio.create_task(osu_api("map", map_id=score.beatmap.id))
    if not osu.exists():
        await download_osu(score.beatmap.set_id, score.beatmap.id)
    info = await task1
    user_path = user_cache_path / str(info.id)
    if not user_path.exists():
        user_path.mkdir(parents=True, exist_ok=True)
    map_json = await task2
    # 判断是否开启lazer模式
    if source == "osu":
        score = cal_score_info(is_lazer, score)
    return await draw_score_pic(score, info, map_json, "", is_lazer, source)


async def get_score_data(
    uid: int,
    is_lazer: bool,
    mode: Optional[str],
    mods: Optional[list[str]],
    mapid: int = 0,
    source: str = "osu",
) -> BytesIO:
    grank = ""
    task = asyncio.create_task(get_user_info_data(uid, mode, source))
    map_json = await osu_api("map", map_id=mapid)
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
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(map_json["beatmapset_id"], mapid)
    info = await task
    user_path = user_cache_path / str(info.id)
    if not user_path.exists():
        user_path.mkdir(parents=True, exist_ok=True)
    # 判断是否开启lazer模式
    if source == "osu":
        score = cal_score_info(is_lazer, score)
    return await draw_score_pic(score, info, map_json, grank, is_lazer, source)


async def draw_score_pic(score_info: UnifiedScore, info: UnifiedUser, map_json, grank, is_lazer, source) -> BytesIO:
    mapinfo = Beatmap(**map_json)
    original_mapinfo = mapinfo.copy()
    mapinfo = with_mods(mapinfo, score_info, score_info.mods)
    path = map_path / str(mapinfo.beatmapset_id)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    # pp
    osu = path / f"{mapinfo.id}.osu"
    pp_info = cal_pp(score_info, str(osu.absolute()), is_lazer)
    original_ss_pp_info = get_ss_pp(str(osu.absolute()), 0, is_lazer)
    if_pp, ss_pp = get_if_pp_ss_pp(score_info, str(osu.absolute()), is_lazer)
    # 新建图片
    im = Image.new("RGBA", (1280, 720))
    draw = ImageDraw.Draw(im)
    # 获取cover并裁剪，高斯，降低亮度
    try:
        bg = await get_bg(mapinfo.id, mapinfo.beatmapset_id)
        cover_crop_left = await crop_bg((1280, 720), bg)
        cover_gb_left = cover_crop_left.filter(ImageFilter.GaussianBlur(10))
        cover_gb_left = ImageEnhance.Brightness(cover_gb_left).enhance(1)
        cover_img_left = ImageEnhance.Brightness(cover_gb_left).enhance(2 / 4.0)
        im.alpha_composite(cover_img_left, (0, 0))
        # 新小图 BG
        cover_crop_right = await crop_bg((650, 270), bg)
        cover_gb_right = cover_crop_right.filter(ImageFilter.GaussianBlur(1))
        cover_gb_right = ImageEnhance.Brightness(cover_gb_right).enhance(0.9)
        cover_img_right = ImageEnhance.Brightness(cover_gb_right).enhance(1)
        cover_img_right = draw_fillet(cover_img_right, 15)
        im.alpha_composite(cover_img_right, (0, 50))
    except NetworkError:
        ...
    # 获取成绩背景做底图
    bg = get_modeimage(score_info.ruleset_id)
    recent_bg = Image.open(bg).convert("RGBA")
    im.alpha_composite(recent_bg)
    # 模式
    draw_text_with_outline(
        draw,
        (30, 80),
        IconLs[score_info.ruleset_id],
        extra_30,
        anchor="lm",
        fill=(255, 255, 255, 255),
    )
    # 难度星星
    stars_bg = stars_diff(pp_info.difficulty.stars, Stars)
    stars_img = stars_bg.resize((85, 37))
    im.alpha_composite(stars_img, (552, 67))
    # 难度竖条
    star_bg = stars_diff(pp_info.difficulty.stars, Stardiff)
    star_img = star_bg.resize((20, 271))
    im.alpha_composite(star_img, (0, 50))
    # 星级
    if pp_info.difficulty.stars < 6.5:
        color = (0, 0, 0, 255)
    else:
        color = (255, 217, 102, 255)

    draw.text(
        (556, 85),
        f"★{pp_info.difficulty.stars:.2f}",
        font=Torus_SemiBold_20,
        anchor="lm",
        fill=color,
    )
    # mods
    # if any(i in score_info.mods for i in (Mod(acronym="HD"), Mod(acronym="FL"), Mod(acronym="FI"))):
    # ranking = ["XH", "SH", "A", "B", "C", "D", "F"]
    # else:
    # ranking = ["X", "S", "A", "B", "C", "D", "F"]
    if score_info.mods:
        for mods_num, s_mods in enumerate(score_info.mods):
            mods_bg = osufile / "mods" / f"{s_mods.acronym}.png"
            try:
                mods_img = Image.open(mods_bg).convert("RGBA")
                im.alpha_composite(mods_img, (880 + 50 * mods_num, 100))
            except FileNotFoundError:
                pass
    # 成绩S-F
    # rank_ok = False
    # for rank_num, i in enumerate(ranking):
    # rank_img = osufile / "ranking" / f"ranking-{i}.png"
    # if rank_ok:
    # rank_b = Image.open(rank_img).convert("RGBA").resize((48, 24))
    # rank_new = Image.new("RGBA", rank_b.size, (0, 0, 0, 0))
    # rank_bg = Image.blend(rank_new, rank_b, 0.5)
    # elif i != score_info.rank:
    # rank_b = Image.open(rank_img).convert("RGBA").resize((48, 24))
    # rank_new = Image.new("RGBA", rank_b.size, (0, 0, 0, 0))
    # rank_bg = Image.blend(rank_new, rank_b, 0.2)
    # else:
    # rank_bg = Image.open(rank_img).convert("RGBA").resize((48, 24))
    # rank_ok = True
    # im.alpha_composite(rank_bg, (75, 163 + 39 * rank_num))
    # 成绩+acc
    im = draw_acc(im, score_info.accuracy, score_info.ruleset_id)
    # 地区
    country = osufile / "flags" / f"{info.country_code}.png"
    country_bg = Image.open(country).convert("RGBA").resize((66, 45))
    im.alpha_composite(country_bg, (208, 597))
    if info.team and info.team.flag_url:
        team_path = team_cache_path / f"{info.team.id}.png"
        if not team_path.exists():
            team_img = await get_projectimg(info.team.flag_url)
            team_img = Image.open(team_img).convert("RGBA")
            team_img.save(team_path)
        try:
            team_img = Image.open(team_path).convert("RGBA").resize((80, 40))
            im.alpha_composite(team_img, (208, 660))
        except UnidentifiedImageError:
            team_path.unlink()
            raise NetworkError("team 图片下载错误，请重试！")
        draw.text((297, 675), info.team.name, font=Torus_Regular_20, anchor="lt")
    # supporter
    # if info.is_supporter:
    #     im.alpha_composite(SupporterBg.resize((40, 40)), (250, 640))
    # 处理mania转谱cs
    if score_info.ruleset_id == 3 and mapinfo.mode == 0:
        temp_accuracy = mapinfo.accuracy
        convert = (mapinfo.count_sliders + mapinfo.count_spinners) / (
            mapinfo.count_circles + mapinfo.count_sliders + mapinfo.count_spinners
        )
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
    # cs, ar, od, hp
    mapdiff = [mapinfo.cs, mapinfo.drain, mapinfo.accuracy, mapinfo.ar]
    original_mapdiff = [
        original_mapinfo.cs,
        original_mapinfo.drain,
        original_mapinfo.accuracy,
        original_mapinfo.ar,
    ]

    for num, (orig, new) in enumerate(zip(original_mapdiff, mapdiff)):
        orig_difflen = int(400 * max(0, orig) / 10) if orig <= 10 else 400
        new_difflen = int(400 * max(0, new) / 10) if new <= 10 else 400
        if is_close(new, orig):
            color = (255, 255, 255, 255)
            diff_len = Image.new("RGBA", (orig_difflen, 8), color)
            im.alpha_composite(diff_len, (165, 352 + 35 * num))
        elif new > orig and not (score_info.ruleset_id == 3 and mapinfo.mode == "osu"):
            color = (198, 92, 102, 255)
            orig_color = (246, 136, 144, 255)
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (165, 352 + 35 * num))
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (165, 352 + 35 * num))
        elif new < orig and not (score_info.ruleset_id == 3 and mapinfo.mode == "osu"):
            color = (161, 212, 238, 255)
            orig_color = (255, 255, 255, 255)
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (165, 352 + 35 * num))
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (165, 352 + 35 * num))
        else:
            raise Exception("没有这种情况")
        if new == round(new):
            draw.text(
                (610, 355 + 35 * num),
                f"{new:.0f}",
                font=Torus_SemiBold_20,
                anchor="mm",
            )
        else:
            draw.text(
                (610, 355 + 35 * num),
                f"{new:.2f}" if new != round(new, 1) else f"{new:.1f}",
                font=Torus_SemiBold_20,
                anchor="mm",
            )
    # stardiff
    stars = pp_info.difficulty.stars
    original_stars = original_ss_pp_info.difficulty.stars
    if stars > original_stars:
        color = (198, 92, 102, 255)
        orig_color = (246, 111, 34, 255)
        new_difflen = int(400 * max(0.0, stars) / 10) if stars <= 10 else 400
        new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
        im.alpha_composite(new_diff_len, (165, 490))
        orig_difflen = int(400 * max(0.0, original_stars) / 10) if original_stars <= 10 else 400
        orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
        im.alpha_composite(orig_diff_len, (165, 490))
    elif stars < original_stars:
        color = (161, 187, 127, 255)
        orig_color = (255, 204, 34, 255)
        orig_difflen = int(400 * max(0.0, original_stars) / 10) if original_stars <= 10 else 400
        orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
        im.alpha_composite(orig_diff_len, (165, 490))
        new_difflen = int(400 * max(0.0, stars) / 10) if stars <= 10 else 400
        new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
        im.alpha_composite(new_diff_len, (165, 490))
    else:
        color = (255, 204, 34, 255)
        difflen = int(400 * stars / 10) if stars <= 10 else 400
        diff_len = Image.new("RGBA", (difflen, 8), color)
        im.alpha_composite(diff_len, (165, 490))
    draw.text((610, 493), f"{stars:.2f}", font=Torus_SemiBold_20, anchor="mm")
    # 时长 - 滑条
    diff_info = [
        calc_songlen(mapinfo.total_length),
        f"{mapinfo.bpm:.1f}",
        mapinfo.count_circles,
        mapinfo.count_sliders,
    ] + ([mapinfo.count_spinners] if score_info.ruleset_id != 3 else [])
    for num, i in enumerate(diff_info):
        draw_text_with_outline(
            draw,
            (70 + 120 * num, 300),
            f"{i}",
            font=Torus_Regular_20,
            anchor="lm",
            fill=(255, 204, 34, 255),
        )
    # 状态
    draw_text_with_outline(
        draw,
        (595, 115),
        mapinfo.status.capitalize(),
        Torus_SemiBold_15,
        anchor="mm",
        fill=(255, 255, 255, 255),
    )
    # setid
    draw.text((32, 25), f"Setid：{mapinfo.beatmapset_id}", font=Torus_SemiBold_20, anchor="lm")
    # mapid
    draw.text((650, 25), f"Mapid: {mapinfo.id}", font=Torus_SemiBold_20, anchor="rm")
    # 曲名
    title = trim_text_with_ellipsis(mapinfo.beatmapset.title, 600, Torus_SemiBold_30)
    draw_text_with_outline(
        draw,
        (30, 200),
        title,
        Torus_SemiBold_30,
        anchor="lm",
        fill=(255, 255, 255, 255),
    )
    # 艺术家
    artist = trim_text_with_ellipsis(mapinfo.beatmapset.artist, 600, Torus_SemiBold_20)
    draw_text_with_outline(
        draw,
        (30, 230),
        artist,
        Torus_SemiBold_20,
        anchor="lm",
        fill=(255, 255, 255, 255),
    )
    # mapper
    if mapinfo.owners:
        owner_names = [owner.username for owner in mapinfo.owners]
        owners_str = ", ".join(owner_names)
        mapper = f"谱师: {owners_str}"

    else:
        mapper = f"谱师: {mapinfo.beatmapset.creator}"
    mapper = trim_text_with_ellipsis(mapper, 600, Torus_SemiBold_15)
    draw_text_with_outline(
        draw,
        (30, 265),
        mapper,
        Torus_SemiBold_15,
        anchor="lm",
        fill=(255, 255, 255, 255),
    )
    # 谱面版本
    version = trim_text_with_ellipsis(mapinfo.version, 450, Torus_SemiBold_15)
    draw_text_with_outline(
        draw,
        (65, 80),
        version,
        Torus_SemiBold_15,
        anchor="lm",
        fill=(255, 255, 255, 255),
    )
    # 评价
    draw.text((772, 185), score_info.rank, font=Venera_60, anchor="mm")
    # 分数
    draw.text(
        (880, 165),
        f"{score_info.legacy_total_score or score_info.total_score:,}",
        font=Torus_Regular_60,
        anchor="lm",
    )
    # 时间
    draw.text((883, 230), "达成时间：", font=Torus_SemiBold_20, anchor="lm")
    draw.text((985, 230), score_info.ended_at.strftime("%Y-%m-%d %H:%M:%S"), font=Torus_SemiBold_20, anchor="lm")
    # 全球排名
    draw.text((883, 260), "全球排行：" if grank else "", font=Torus_SemiBold_20, anchor="lm")
    draw.text((985, 260), f"#{grank}" if grank else "", font=Torus_SemiBold_25, anchor="lm")
    # 左下玩家名
    draw.text((208, 550), info.username, font=Torus_SemiBold_30, anchor="lm")
    # 国内排名
    draw.text(
        (283, 630),
        f"#{info.statistics.country_rank}",
        font=Torus_SemiBold_25,
        anchor="lm",
    )
    if score_info.ruleset_id in {0, 4, 8}:
        draw.text((1066, 393), ss_pp, font=Torus_Regular_25, anchor="mm")
        draw.text((933, 393), if_pp, font=Torus_Regular_25, anchor="mm")
        draw.text((768, 438), f"{pp_info.pp:.0f}", font=Torus_Regular_50, anchor="mm")
        draw.text((933, 482), f"{pp_info.pp_aim:.0f}", font=Torus_Regular_25, anchor="mm")
        draw.text((1066, 482), f"{pp_info.pp_speed:.0f}", font=Torus_Regular_25, anchor="mm")
        draw.text((1200, 482), f"{pp_info.pp_accuracy:.0f}", font=Torus_Regular_25, anchor="mm")
        draw.text(
            (768, 577),
            f"{score_info.accuracy:.2f}%",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (768, 666),
            f"{score_info.max_combo:,}/{pp_info.difficulty.max_combo}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (933, 577),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1066, 577),
            f"{score_info.statistics.ok or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (933, 666),
            f"{score_info.statistics.meh or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1066, 666),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
    elif score_info.ruleset_id in {1, 5}:
        draw.text(
            (768, 577),
            f"{score_info.accuracy:.2f}%",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text((768, 666), f"{score_info.max_combo:,}", font=Torus_Regular_25, anchor="mm")
        draw.text((768, 438), f"{pp_info.pp:.0f}", font=Torus_Regular_50, anchor="mm")
        draw.text((933, 393), f"{ss_pp}", font=Torus_Regular_25, anchor="mm")
        draw.text(
            (933, 577),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1066, 577),
            f"{score_info.statistics.ok or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (933, 666),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
    elif score_info.ruleset_id in {2, 6}:
        draw.text(
            (768, 577),
            f"{score_info.accuracy:.2f}%",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (768, 666),
            f"{score_info.max_combo}/{pp_info.difficulty.max_combo}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text((768, 438), f"{pp_info.pp:.0f}", font=Torus_Regular_50, anchor="mm")
        draw.text((933, 393), f"{ss_pp}", font=Torus_Regular_25, anchor="mm")
        draw.text(
            (933, 577),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1066, 577),
            f"{score_info.statistics.large_tick_hit or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (933, 666),
            f"{score_info.statistics.small_tick_miss or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1066, 666),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
    else:
        draw.text(
            (933, 600),
            (
                f"{score_info.statistics.perfect / score_info.statistics.great:.1f}:1"
                if (score_info.statistics.great or 0) != 0
                else "∞:1"
            ),
            font=Torus_Regular_15,
            anchor="mm",
        )
        draw.text(
            (768, 577),
            f"{score_info.accuracy:.2f}%",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text((768, 666), f"{score_info.max_combo}", font=Torus_Regular_25, anchor="mm")
        draw.text((768, 438), f"{pp_info.pp:.0f}", font=Torus_Regular_50, anchor="mm")
        draw.text((933, 393), f"{ss_pp}", font=Torus_Regular_25, anchor="mm")
        draw.text(
            (933, 577),
            f"{score_info.statistics.perfect or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1066, 577),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1200, 577),
            f"{score_info.statistics.good or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (933, 666),
            f"{score_info.statistics.ok or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1066, 666),
            f"{score_info.statistics.meh or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
        draw.text(
            (1200, 666),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_25,
            anchor="mm",
        )
    user_icon = await open_user_icon(info, source)
    _ = asyncio.create_task(update_map(mapinfo.beatmapset_id, mapinfo.id))
    _ = asyncio.create_task(update_icon(info))
    gif_frames = []
    if not getattr(user_icon, "is_animated", False):
        icon_bg = user_icon.convert("RGBA").resize((170, 170))
        icon_img = draw_fillet(icon_bg, 15)
        im.alpha_composite(icon_img, (27, 532))
        byt = BytesIO()
        im.convert("RGB").save(byt, "jpeg")
        im.close()
        user_icon.close()
        return byt
    for gif_frame in ImageSequence.Iterator(user_icon):
        # 将 GIF 图片中的每一帧转换为 RGBA 模式
        gif_frame = gif_frame.convert("RGBA").resize((170, 170))
        gif_frame = draw_fillet(gif_frame, 15)
        # 创建一个新的 RGBA 图片，将 PNG 图片作为背景，将当前帧添加到背景上
        rgba_frame = Image.new("RGBA", im.size, (0, 0, 0, 0))
        rgba_frame.paste(im, (0, 0), im)
        rgba_frame.paste(gif_frame, (27, 532), gif_frame)
        # 将 RGBA 图片转换为 RGB 模式，并添加到 GIF 图片中
        gif_frames.append(rgba_frame)
    gif_bytes = BytesIO()
    # 保存 GIF 图片
    gif_frames[0].save(
        gif_bytes,
        format="gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=user_icon.info["duration"],
    )
    # 输出
    gif_frames[0].close()
    user_icon.close()
    return gif_bytes


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


def cal_score_info(is_lazer: bool, score_info: UnifiedScore) -> UnifiedScore:
    if is_lazer:
        score_info.legacy_total_score = score_info.total_score
    if score_info.ruleset_id == 3 and not is_lazer:
        score_info.accuracy = cal_legacy_acc(score_info.statistics)
    if not is_lazer:
        is_hidden = any(i in score_info.mods for i in (Mod(acronym="HD"), Mod(acronym="FL"), Mod(acronym="FI")))
        score_info.rank = cal_legacy_rank(score_info, is_hidden)
    return score_info
