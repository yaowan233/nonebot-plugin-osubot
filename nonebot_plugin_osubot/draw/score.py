import asyncio
from io import BytesIO
from typing import Union, Optional
from datetime import datetime, timedelta

from PIL import ImageDraw, ImageFilter, ImageEnhance, ImageSequence

from ..utils import GMN
from ..api import osu_api
from ..info import get_bg
from ..mods import get_mods_list
from ..database.models import UserData
from ..beatmap_stats_moder import with_mods
from ..schema import User, Beatmap, NewScore
from ..schema.score import Mod, NewStatistics
from ..pp import cal_pp, get_ss_pp, get_if_pp_ss_pp
from ..file import map_path, download_osu, user_cache_path
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
)
from .static import (
    Image,
    IconLs,
    Venera_75,
    SupporterBg,
    Torus_Regular_20,
    Torus_Regular_30,
    Torus_Regular_75,
    Torus_SemiBold_20,
    Torus_SemiBold_25,
    Torus_SemiBold_30,
    osufile,
    extra_30,
)


async def draw_score(
    project: str,
    uid: int,
    user_id: int,
    mode: str,
    mods: Optional[list[str]],
    best: int = 0,
    mapid: int = 0,
    is_name: bool = False,
) -> Union[str, BytesIO]:
    user = await UserData.get_or_none(user_id=user_id)
    lazer_mode = True if not user else user.lazer_mode
    task0 = asyncio.create_task(
        osu_api(
            project,
            uid,
            mode,
            mapid,
            is_name=is_name,
            limit=100,
            legacy_only=int(not lazer_mode),
        )
    )
    task1 = asyncio.create_task(osu_api("info", uid, mode, is_name=is_name))
    score_json = await task0
    if not score_json:
        return f"未查询到在 {GMN[mode]} 的游玩记录"
    elif isinstance(score_json, str):
        return score_json
    if not lazer_mode:
        score_json = [i for i in score_json if {"acronym": "CL"} in i["mods"]]
    if project in ("recent", "pr"):
        if len(score_json) <= best:
            return f"未查询到24小时内在 {GMN[mode]} 中第{best + 1}个游玩记录"
        score_info = NewScore(**score_json[best])
    elif project == "bp":
        score_ls = [NewScore(**i) for i in score_json]
        mods_ls = get_mods_list(score_ls, mods)
        if len(mods_ls) < best:
            return f'未找到开启 {"|".join(mods)} Mods的第{best}个成绩'
        score_info = NewScore(**score_json[mods_ls[best - 1]])
    else:
        raise Exception("Project Error")
    # 从官网获取信息
    path = map_path / str(score_info.beatmap.beatmapset_id)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{score_info.beatmap.id}.osu"
    task2 = asyncio.create_task(osu_api("map", map_id=score_info.beatmap.id))
    if not osu.exists():
        await download_osu(score_info.beatmap.beatmapset_id, score_info.beatmap.id)
    info_json = await task1
    if isinstance(info_json, str):
        return info_json
    info = User(**info_json)
    user_path = user_cache_path / str(info.id)
    if not user_path.exists():
        user_path.mkdir(parents=True, exist_ok=True)
    map_json = await task2
    if isinstance(map_json, str):
        return map_json
    # 判断是否开启lazer模式
    score_info = cal_score_info(lazer_mode, score_info)
    return await draw_score_pic(
        score_info,
        info,
        map_json,
        "",
    )


async def get_score_data(
    uid: int,
    user_id: int,
    mode: str,
    mods: Optional[list[str]],
    mapid: int = 0,
    is_name: bool = False,
):
    grank = ""
    if mods:
        task0 = asyncio.create_task(osu_api("score", uid, mode, mapid, is_name=is_name))
    else:
        task0 = asyncio.create_task(osu_api("best_score", uid, mode, mapid, is_name=is_name))
    task1 = asyncio.create_task(osu_api("info", uid, mode, is_name=is_name))
    task2 = asyncio.create_task(osu_api("map", map_id=mapid))
    score_json = await task0
    if not score_json:
        return f"未查询到在 {GMN[mode]} 的游玩记录"
    elif isinstance(score_json, str):
        return score_json
    if not mods:
        grank = score_json.get("position", "")
        score_ls = [NewScore(**score_json["score"])]
    else:
        score_ls = [NewScore(**i) for i in score_json["scores"]]
    user = await UserData.get_or_none(user_id=user_id)
    lazer_mode = True if not user else user.lazer_mode
    if not lazer_mode:
        score_ls = [i for i in score_ls if Mod(acronym="CL") in i.mods]
        for i in score_ls:
            i.mods.remove(Mod(acronym="CL"))
    if not score_ls:
        return f"未查询到在 {GMN[mode]} 的游玩记录"
    if mods:
        for score in score_ls:
            if mods == "NM" and not score.mods:
                score_info = score
                break
            if score.mods == [Mod(acronym=i) for i in mods]:
                score_info = score
                break
        else:
            score_ls.sort(key=lambda x: x.legacy_total_score, reverse=True)
            for score in score_ls:
                if set(mods).issubset(i.acronym for i in score.mods):
                    score_info = score
                    break
            else:
                return f'未找到开启 {"|".join(mods)} Mods的成绩'
    else:
        score_info = score_ls[0]
    map_json = await task2
    if isinstance(map_json, str):
        return map_json
    path = map_path / str(map_json["beatmapset_id"])
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(map_json["beatmapset_id"], mapid)
    info_json = await task1
    info = User(**info_json)
    user_path = user_cache_path / str(info.id)
    if not user_path.exists():
        user_path.mkdir(parents=True, exist_ok=True)
    # 判断是否开启lazer模式
    score_info = cal_score_info(lazer_mode, score_info)
    return await draw_score_pic(
        score_info,
        info,
        map_json,
        grank,
    )


async def draw_score_pic(score_info: NewScore, info, map_json, grank) -> BytesIO:
    mapinfo = Beatmap(**map_json)
    original_mapinfo = mapinfo.copy()
    mapinfo = with_mods(mapinfo, score_info, score_info.mods)
    path = map_path / str(mapinfo.beatmapset_id)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    # pp
    osu = path / f"{mapinfo.id}.osu"
    pp_info = cal_pp(score_info, str(osu.absolute()))
    original_ss_pp_info = get_ss_pp(str(osu.absolute()), 0)
    if_pp, ss_pp = get_if_pp_ss_pp(score_info, str(osu.absolute()))
    # 新建图片
    im = Image.new("RGBA", (1500, 720))
    draw = ImageDraw.Draw(im)
    # 获取cover并裁剪，高斯，降低亮度
    bg = await get_bg(mapinfo.id, mapinfo.beatmapset_id)
    cover_crop = await crop_bg((1500, 720), bg)
    cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(3))
    cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
    im.alpha_composite(cover_img, (0, 0))
    # 获取成绩背景做底图
    bg = get_modeimage(score_info.ruleset_id)
    recent_bg = Image.open(bg).convert("RGBA")
    im.alpha_composite(recent_bg)
    # 模式
    draw.text((75, 75), IconLs[score_info.ruleset_id], font=extra_30, anchor="lt")
    # 难度星星
    stars_bg = stars_diff(pp_info.difficulty.stars)
    stars_img = stars_bg.resize((85, 37))
    im.alpha_composite(stars_img, (122, 72))
    if pp_info.difficulty.stars < 6.5:
        color = (0, 0, 0, 255)
    else:
        color = (255, 217, 102, 255)
    # 星级
    draw.text(
        (128, 90),
        f"★{pp_info.difficulty.stars:.2f}",
        font=Torus_SemiBold_20,
        anchor="lm",
        fill=color,
    )
    # mods
    if any(i in score_info.mods for i in (Mod(acronym="HD"), Mod(acronym="FL"), Mod(acronym="FI"))):
        ranking = ["XH", "SH", "A", "B", "C", "D", "F"]
    else:
        ranking = ["X", "S", "A", "B", "C", "D", "F"]
    if score_info.mods:
        for mods_num, s_mods in enumerate(score_info.mods):
            mods_bg = osufile / "mods" / f"{s_mods.acronym}.png"
            try:
                mods_img = Image.open(mods_bg).convert("RGBA")
                im.alpha_composite(mods_img, (500 + 50 * mods_num, 160))
            except FileNotFoundError:
                pass
    # 成绩S-F
    rank_ok = False
    for rank_num, i in enumerate(ranking):
        rank_img = osufile / "ranking" / f"ranking-{i}.png"
        if rank_ok:
            rank_b = Image.open(rank_img).convert("RGBA").resize((48, 24))
            rank_new = Image.new("RGBA", rank_b.size, (0, 0, 0, 0))
            rank_bg = Image.blend(rank_new, rank_b, 0.5)
        elif i != score_info.rank:
            rank_b = Image.open(rank_img).convert("RGBA").resize((48, 24))
            rank_new = Image.new("RGBA", rank_b.size, (0, 0, 0, 0))
            rank_bg = Image.blend(rank_new, rank_b, 0.2)
        else:
            rank_bg = Image.open(rank_img).convert("RGBA").resize((48, 24))
            rank_ok = True
        im.alpha_composite(rank_bg, (75, 163 + 39 * rank_num))
    # 成绩+acc
    im = draw_acc(im, score_info.accuracy, score_info.ruleset_id)
    # 地区
    country = osufile / "flags" / f"{info.country_code}.png"
    country_bg = Image.open(country).convert("RGBA").resize((66, 45))
    im.alpha_composite(country_bg, (250, 577))
    # supporter
    if info.is_supporter:
        im.alpha_composite(SupporterBg.resize((40, 40)), (250, 640))
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
        orig_difflen = int(250 * max(0, orig) / 10) if orig <= 10 else 250
        new_difflen = int(250 * max(0, new) / 10) if new <= 10 else 250
        if is_close(new, orig):
            color = (255, 255, 255, 255)
            diff_len = Image.new("RGBA", (orig_difflen, 8), color)
            im.alpha_composite(diff_len, (1190, 306 + 35 * num))
        elif new > orig and not (score_info.ruleset_id == 3 and mapinfo.mode == "osu"):
            color = (198, 92, 102, 255)
            orig_color = (246, 136, 144, 255)
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (1190, 306 + 35 * num))
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (1190, 306 + 35 * num))
        elif new < orig and not (score_info.ruleset_id == 3 and mapinfo.mode == "osu"):
            color = (161, 212, 238, 255)
            orig_color = (255, 255, 255, 255)
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (1190, 306 + 35 * num))
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (1190, 306 + 35 * num))
        else:
            raise Exception("没有这种情况")
        if new == round(new):
            draw.text(
                (1470, 310 + 35 * num),
                f"{new:.0f}",
                font=Torus_SemiBold_20,
                anchor="mm",
            )
        else:
            draw.text(
                (1470, 310 + 35 * num),
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
        new_difflen = int(250 * max(0.0, stars) / 10) if stars <= 10 else 250
        new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
        im.alpha_composite(new_diff_len, (1190, 446))
        orig_difflen = int(250 * max(0.0, original_stars) / 10) if original_stars <= 10 else 250
        orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
        im.alpha_composite(orig_diff_len, (1190, 446))
    elif stars < original_stars:
        color = (161, 187, 127, 255)
        orig_color = (255, 204, 34, 255)
        orig_difflen = int(250 * max(0.0, original_stars) / 10) if original_stars <= 10 else 250
        orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
        im.alpha_composite(orig_diff_len, (1190, 446))
        new_difflen = int(250 * max(0.0, stars) / 10) if stars <= 10 else 250
        new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
        im.alpha_composite(new_diff_len, (1190, 446))
    else:
        color = (255, 204, 34, 255)
        difflen = int(250 * stars / 10) if stars <= 10 else 250
        diff_len = Image.new("RGBA", (difflen, 8), color)
        im.alpha_composite(diff_len, (1190, 446))
    draw.text((1470, 450), f"{stars:.2f}", font=Torus_SemiBold_20, anchor="mm")
    # 时长 - 滑条
    diff_info = (
        calc_songlen(mapinfo.total_length),
        f"{mapinfo.bpm:.1f}",
        mapinfo.count_circles,
        mapinfo.count_sliders,
    )
    for num, i in enumerate(diff_info):
        draw.text(
            (1070 + 120 * num, 245),
            f"{i}",
            font=Torus_Regular_20,
            anchor="lm",
            fill=(255, 204, 34, 255),
        )
    # 状态
    draw.text((1400, 184), mapinfo.status.capitalize(), font=Torus_SemiBold_20, anchor="mm")
    # mapid
    draw.text((1485, 90), f"Mapid: {mapinfo.id}", font=Torus_SemiBold_20, anchor="rm")
    # 曲名
    draw.text(
        (75, 38),
        f"{mapinfo.beatmapset.title} | by {mapinfo.beatmapset.artist_unicode}",
        font=Torus_SemiBold_30,
        anchor="lm",
    )
    # 谱面版本，mapper
    draw.text(
        (225, 90),
        f"{mapinfo.version} | 谱师: {mapinfo.beatmapset.creator}",
        font=Torus_SemiBold_20,
        anchor="lm",
    )
    # 评价
    draw.text((316, 307), score_info.rank, font=Venera_75, anchor="mm")
    # 分数
    draw.text(
        (498, 251),
        f"{score_info.legacy_total_score or score_info.total_score:,}",
        font=Torus_Regular_75,
        anchor="lm",
    )
    # 时间
    draw.text((498, 341), "达成时间:", font=Torus_SemiBold_20, anchor="lm")
    old_time = datetime.strptime(score_info.ended_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    new_time = (old_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    draw.text((630, 341), new_time, font=Torus_SemiBold_20, anchor="lm")
    # 全球排名
    draw.text((583, 410), f"#{grank}" if grank else "", font=Torus_SemiBold_25, anchor="mm")
    # 左下玩家名
    draw.text((250, 530), info.username, font=Torus_SemiBold_30, anchor="lm")
    # 国内排名
    draw.text(
        (325, 610),
        f"#{info.statistics.country_rank}",
        font=Torus_SemiBold_25,
        anchor="lm",
    )
    if score_info.ruleset_id == 0:
        draw.text((720, 550), ss_pp, font=Torus_Regular_30, anchor="mm")
        draw.text((840, 550), if_pp, font=Torus_Regular_30, anchor="mm")
        draw.text((960, 550), f"{pp_info.pp:.0f}", font=Torus_Regular_30, anchor="mm")
        draw.text((720, 645), f"{pp_info.pp_aim:.0f}", font=Torus_Regular_30, anchor="mm")
        draw.text((840, 645), f"{pp_info.pp_speed:.0f}", font=Torus_Regular_30, anchor="mm")
        draw.text((960, 645), f"{pp_info.pp_accuracy:.0f}", font=Torus_Regular_30, anchor="mm")
        draw.text(
            (1157, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1385, 550),
            f"{score_info.max_combo:,}/{pp_info.difficulty.max_combo}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1100, 645),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1214, 645),
            f"{score_info.statistics.ok or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1328, 645),
            f"{score_info.statistics.meh or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1442, 645),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    elif score_info.ruleset_id == 1:
        draw.text(
            (1118, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text((1270, 550), f"{score_info.max_combo:,}", font=Torus_Regular_30, anchor="mm")
        draw.text((1420, 550), f"{pp_info.pp:.0f}/{ss_pp}", font=Torus_Regular_30, anchor="mm")
        draw.text(
            (1118, 645),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1270, 645),
            f"{score_info.statistics.ok or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1420, 645),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    elif score_info.ruleset_id == 2:
        draw.text(
            (1083, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1247, 550),
            f"{score_info.max_combo}/{pp_info.difficulty.max_combo}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text((1411, 550), f"{pp_info.pp:.0f}/{ss_pp}", font=Torus_Regular_30, anchor="mm")
        draw.text(
            (1062, 645),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1185, 645),
            f"{score_info.statistics.large_tick_hit or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1309, 645),
            f"{score_info.statistics.small_tick_miss or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1432, 645),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    else:
        draw.text(
            (1002, 580),
            (
                f"{score_info.statistics.perfect / score_info.statistics.great :.1f}:1"
                if (score_info.statistics.great or 0) != 0
                else "∞:1"
            ),
            font=Torus_Regular_20,
            anchor="mm",
        )
        draw.text(
            (1002, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text((1197, 550), f"{score_info.max_combo}", font=Torus_Regular_30, anchor="mm")
        draw.text((1395, 550), f"{pp_info.pp:.0f}/{ss_pp}", font=Torus_Regular_30, anchor="mm")
        draw.text(
            (953, 645),
            f"{score_info.statistics.perfect or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1051, 645),
            f"{score_info.statistics.great or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1150, 645),
            f"{score_info.statistics.good or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1249, 645),
            f"{score_info.statistics.ok or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1347, 645),
            f"{score_info.statistics.meh or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1445, 645),
            f"{score_info.statistics.miss or 0}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    user_icon = await open_user_icon(info)
    _ = asyncio.create_task(update_map(mapinfo.beatmapset_id, mapinfo.id))
    _ = asyncio.create_task(update_icon(info))
    gif_frames = []
    if not getattr(user_icon, "is_animated", False):
        icon_bg = user_icon.convert("RGBA").resize((170, 170))
        icon_img = draw_fillet(icon_bg, 15)
        im.alpha_composite(icon_img, (60, 510))
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
        rgba_frame.paste(gif_frame, (60, 510), gif_frame)
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
        statistics.perfect * 300
        + statistics.great * 300
        + statistics.good * 200
        + statistics.ok * 100
        + statistics.meh * 50
    ) / (num * 300)


def cal_legacy_rank(score_info: NewScore, is_hidden: bool):
    if not score_info.passed:
        return "F"
    great = score_info.statistics.great or 0
    miss = score_info.statistics.miss or 0
    meh = score_info.statistics.meh or 0
    ok = score_info.statistics.ok or 0

    if score_info.ruleset_id == 0:
        max_combo = great + ok + meh + miss
    elif score_info.ruleset_id == 1:
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
        if score_info.accuracy >= 0.95:
            return "SH" if is_hidden else "S"
        elif score_info.accuracy >= 0.9:
            return "A"
        elif score_info.accuracy >= 0.8:
            return "B"
        elif score_info.accuracy >= 0.7:
            return "C"
        else:
            return "D"

    elif score_info.ruleset_id == 2:
        if score_info.accuracy >= 0.98:
            return "SH" if is_hidden else "S"
        elif score_info.accuracy >= 0.94:
            return "A"
        elif score_info.accuracy >= 0.9:
            return "B"
        elif score_info.accuracy >= 0.85:
            return "C"
        else:
            return "D"

    elif score_info.ruleset_id == 1:
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

    elif score_info.ruleset_id == 0:
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


def cal_score_info(is_lazer: bool, score_info: NewScore) -> NewScore:
    if is_lazer:
        score_info.legacy_total_score = score_info.total_score
    if not is_lazer and Mod(acronym="CL") in score_info.mods:
        score_info.mods = [i for i in score_info.mods if i.acronym != "CL"]
    if score_info.ruleset_id == 3 and not is_lazer:
        score_info.accuracy = cal_legacy_acc(score_info.statistics)
    if not is_lazer:
        is_hidden = any(i in score_info.mods for i in (Mod(acronym="HD"), Mod(acronym="FL"), Mod(acronym="FI")))
        score_info.rank = cal_legacy_rank(score_info, is_hidden)
    return score_info
