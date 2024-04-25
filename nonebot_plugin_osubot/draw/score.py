import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Union
from PIL import ImageFilter, ImageEnhance, ImageDraw, ImageSequence

from ..api import osu_api, get_map_bg, get_beatmap_attribute, get_sayo_map_info
from ..beatmap_stats_moder import with_mods
from ..schema import Score, Beatmap, User, BeatmapDifficultyAttributes
from ..mods import get_mods_list
from ..file import re_map, download_osu, user_cache_path, map_path
from ..utils import GMN, FGM
from ..pp import cal_pp, get_if_pp_ss_pp, get_ss_pp

from .static import *
from .utils import (
    draw_acc,
    draw_fillet,
    crop_bg,
    calc_songlen,
    stars_diff,
    get_modeimage,
    open_user_icon,
)


async def draw_score(
    project: str,
    uid: int,
    mode: str,
    mods: Optional[list[str]],
    best: int = 0,
    mapid: int = 0,
    is_name: bool = False,
) -> Union[str, BytesIO]:
    task0 = asyncio.create_task(osu_api(project, uid, mode, mapid, is_name=is_name))
    task1 = asyncio.create_task(osu_api("info", uid, mode, is_name=is_name))
    score_json = await task0
    if not score_json:
        return f"未查询到在 {GMN[mode]} 的游玩记录"
    elif isinstance(score_json, str):
        return score_json
    if project in ("recent", "pr"):
        if len(score_json) < best:
            return f"未查询到24小时内在 {GMN[mode]} 中第{best + 1}个游玩记录"
        score_info = Score(**score_json[best])
        grank = "--"
    elif project == "bp":
        score_ls = [Score(**i) for i in score_json]
        mods_ls = get_mods_list(score_ls, mods)
        if len(mods_ls) < best:
            return f'未找到开启 {"|".join(mods)} Mods的第{best}个成绩'
        score_info = Score(**score_json[mods_ls[best - 1]])
        grank = "--"
    else:
        raise "Project Error"
    # 从官网获取信息
    path = map_path / str(score_info.beatmap.beatmapset_id)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{score_info.beatmap.id}.osu"
    task = asyncio.create_task(get_beatmap_attribute(score_info.beatmap.id, mode))
    task2 = asyncio.create_task(osu_api("map", map_id=score_info.beatmap.id))
    if not osu.exists():
        await download_osu(score_info.beatmap.beatmapset_id, score_info.beatmap.id)
    info_json = await task1
    info = User(**info_json)
    user_path = user_cache_path / str(info.id)
    if not user_path.exists():
        user_path.mkdir(parents=True, exist_ok=True)
    map_json = await task2
    map_attribute_json = await task
    return await draw_score_pic(
        score_info,
        info,
        map_json,
        map_attribute_json,
        score_info.beatmap.id,
        score_info.beatmap.beatmapset_id,
    )


async def get_score_data(
    uid: int,
    mode: str,
    mods: Optional[list[str]],
    mapid: int = 0,
    is_name: bool = False,
):
    task = asyncio.create_task(get_beatmap_attribute(mapid, mode))
    task0 = asyncio.create_task(osu_api("score", uid, mode, mapid, is_name=is_name))
    task1 = asyncio.create_task(osu_api("info", uid, mode, is_name=is_name))
    task2 = asyncio.create_task(osu_api("map", map_id=mapid))
    task3 = asyncio.create_task(get_sayo_map_info(mapid, 1))
    score_json = await task0
    if not score_json:
        return f"未查询到在 {GMN[mode]} 的游玩记录"
    elif isinstance(score_json, str):
        return score_json
    if "score" not in score_json:
        score_ls = [Score(**i) for i in score_json["scores"]]
        if not score_ls:
            return f"未查询到在 {GMN[mode]} 的游玩记录"
        if mods:
            for score in score_ls:
                if mods == "NM" and not score.mods:
                    score_info = score
                    break
                if score.mods == mods:
                    score_info = score
                    break
            else:
                for score in score_ls:
                    if set(mods).issubset(set(score.mods)):
                        score_info = score
                        break
                else:
                    return f'未找到开启 {"|".join(mods)} Mods的成绩'
        else:
            score_info = score_ls[0]
    else:
        score_info = Score(**score_json["score"])
    sayo_map_info = await task3
    path = map_path / str(sayo_map_info.data.sid)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(sayo_map_info.data.sid, mapid)
    info_json = await task1
    info = User(**info_json)
    user_path = user_cache_path / str(info.id)
    if not user_path.exists():
        user_path.mkdir(parents=True, exist_ok=True)
    map_json = await task2
    map_attribute_json = await task
    return await draw_score_pic(
        score_info, info, map_json, map_attribute_json, mapid, sayo_map_info.data.sid
    )


async def draw_score_pic(
    score_info, info, map_json, map_attribute_json, bid, sid
) -> BytesIO:
    mapinfo = Beatmap(**map_json)
    original_mapinfo = mapinfo.copy()
    mapinfo = with_mods(mapinfo, score_info, score_info.mods)
    path = map_path / str(sid)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    # pp
    osu = path / f"{bid}.osu"
    pp_info = cal_pp(score_info, str(osu.absolute()))
    original_ss_pp_info = get_ss_pp(str(osu.absolute()), 0)
    if_pp, ss_pp = get_if_pp_ss_pp(score_info, str(osu.absolute()))
    # 新建图片
    im = Image.new("RGBA", (1500, 720))
    draw = ImageDraw.Draw(im)
    # 获取cover并裁剪，高斯，降低亮度
    cover = re_map(osu)
    cover_path = path / cover
    if not cover_path.exists():
        if bg := await get_map_bg(bid, sid, cover):
            with open(cover_path, "wb") as f:
                f.write(bg.getvalue())
    cover_crop = await crop_bg("BG", cover_path)
    cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(3))
    cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
    im.alpha_composite(cover_img, (0, 0))
    # 获取成绩背景做底图
    bg = get_modeimage(FGM[score_info.mode])
    recent_bg = Image.open(bg).convert("RGBA")
    im.alpha_composite(recent_bg)
    # 模式
    draw.text((75, 75), IconLs[score_info.mode], font=extra_30, anchor="lt")
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
    if "HD" in score_info.mods or "FL" in score_info.mods:
        ranking = ["XH", "SH", "A", "B", "C", "D", "F"]
    else:
        ranking = ["X", "S", "A", "B", "C", "D", "F"]
    if score_info.mods:
        for mods_num, s_mods in enumerate(score_info.mods):
            mods_bg = osufile / "mods" / f"{s_mods}.png"
            mods_img = Image.open(mods_bg).convert("RGBA")
            im.alpha_composite(mods_img, (500 + 50 * mods_num, 160))
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
    im = draw_acc(im, score_info.accuracy, score_info.mode)
    # 地区
    country = osufile / "flags" / f"{info.country_code}.png"
    country_bg = Image.open(country).convert("RGBA").resize((66, 45))
    im.alpha_composite(country_bg, (250, 577))
    # supporter
    if info.is_supporter:
        im.alpha_composite(SupporterBg.resize((40, 40)), (250, 640))
    map_attribute = BeatmapDifficultyAttributes(**map_attribute_json["attributes"])
    # 处理mania转谱cs
    if score_info.mode == "mania" and mapinfo.mode == "osu":
        temp_accuracy = mapinfo.accuracy
        convert = (mapinfo.count_sliders + mapinfo.count_spinners) / (
            mapinfo.count_circles + mapinfo.count_sliders + mapinfo.count_spinners
        )
        convert_od = round(temp_accuracy)
        if (
            convert < 0.20
            or (convert < 0.30 or round(mapinfo.cs) >= 5)
            and convert_od > 5
        ):
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
        if new > orig and not (score_info.mode == "mania" and mapinfo.mode == "osu"):
            color = (198, 92, 102, 255)
            orig_color = (246, 136, 144, 255)
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (1190, 306 + 35 * num))
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (1190, 306 + 35 * num))
        elif new < orig and not (score_info.mode == "mania" and mapinfo.mode == "osu"):
            color = (161, 212, 238, 255)
            orig_color = (255, 255, 255, 255)
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (1190, 306 + 35 * num))
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (1190, 306 + 35 * num))
        else:
            color = (255, 255, 255, 255)
            diff_len = Image.new("RGBA", (orig_difflen, 8), color)
            im.alpha_composite(diff_len, (1190, 306 + 35 * num))
        if new == round(new):
            draw.text(
                (1470, 310 + 35 * num),
                "%.0f" % new,
                font=Torus_SemiBold_20,
                anchor="mm",
            )
        else:
            draw.text(
                (1470, 310 + 35 * num),
                "%.2f" % new if new != round(new, 1) else "%.1f" % new,
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
        orig_difflen = (
            int(250 * max(0.0, original_stars) / 10) if original_stars <= 10 else 250
        )
        orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
        im.alpha_composite(orig_diff_len, (1190, 446))
    elif stars < original_stars:
        color = (161, 187, 127, 255)
        orig_color = (255, 204, 34, 255)
        orig_difflen = (
            int(250 * max(0.0, original_stars) / 10) if original_stars <= 10 else 250
        )
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
    draw.text(
        (1400, 184), mapinfo.status.capitalize(), font=Torus_SemiBold_20, anchor="mm"
    )
    # mapid
    draw.text((1485, 90), f"Mapid: {bid}", font=Torus_SemiBold_20, anchor="rm")
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
    draw.text((498, 251), f"{score_info.score:,}", font=Torus_Regular_75, anchor="lm")
    # 时间
    draw.text((498, 341), "达成时间:", font=Torus_SemiBold_20, anchor="lm")
    old_time = datetime.strptime(
        score_info.created_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"
    )
    new_time = (old_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    draw.text((630, 341), new_time, font=Torus_SemiBold_20, anchor="lm")
    # 全球排名
    # draw.text((583, 410), grank, font=Torus_SemiBold_25, anchor='mm')
    # 左下玩家名
    draw.text((250, 530), info.username, font=Torus_SemiBold_30, anchor="lm")
    # 国内排名
    draw.text(
        (325, 610),
        f"#{info.statistics.country_rank}",
        font=Torus_SemiBold_25,
        anchor="lm",
    )
    if score_info.mode == "osu":
        draw.text((720, 550), ss_pp, font=Torus_Regular_30, anchor="mm")
        draw.text((840, 550), if_pp, font=Torus_Regular_30, anchor="mm")
        draw.text((960, 550), f"{pp_info.pp:.0f}", font=Torus_Regular_30, anchor="mm")
        draw.text(
            (720, 645), f"{pp_info.pp_aim:.0f}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (840, 645), f"{pp_info.pp_speed:.0f}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (960, 645), f"{pp_info.pp_acc:.0f}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (1157, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1385, 550),
            f"{score_info.max_combo:,}/{map_attribute.max_combo:,}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1100, 645),
            f"{score_info.statistics.count_300}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1214, 645),
            f"{score_info.statistics.count_100}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1328, 645),
            f"{score_info.statistics.count_50}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1442, 645),
            f"{score_info.statistics.count_miss}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    elif score_info.mode == "taiko":
        draw.text(
            (1118, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1270, 550), f"{score_info.max_combo:,}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (1420, 550), f"{pp_info.pp:.0f}/{ss_pp}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (1118, 645),
            f"{score_info.statistics.count_300}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1270, 645),
            f"{score_info.statistics.count_100}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1420, 645),
            f"{score_info.statistics.count_miss}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    elif score_info.mode == "fruits":
        draw.text(
            (1083, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1247, 550),
            f"{score_info.max_combo}/{map_attribute.max_combo}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1411, 550), f"{pp_info.pp:.0f}/{ss_pp}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (1062, 645),
            f"{score_info.statistics.count_300}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1185, 645),
            f"{score_info.statistics.count_100}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1309, 645),
            f"{score_info.statistics.count_katu}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1432, 645),
            f"{score_info.statistics.count_miss}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    else:
        draw.text(
            (1002, 580),
            f"{score_info.statistics.count_geki / score_info.statistics.count_300 :.1f}:1"
            if score_info.statistics.count_300 != 0
            else "∞:1",
            font=Torus_Regular_20,
            anchor="mm",
        )
        draw.text(
            (1002, 550),
            f"{score_info.accuracy * 100:.2f}%",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1197, 550), f"{score_info.max_combo}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (1395, 550), f"{pp_info.pp:.0f}/{ss_pp}", font=Torus_Regular_30, anchor="mm"
        )
        draw.text(
            (953, 645),
            f"{score_info.statistics.count_geki}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1051, 645),
            f"{score_info.statistics.count_300}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1150, 645),
            f"{score_info.statistics.count_katu}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1249, 645),
            f"{score_info.statistics.count_100}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1347, 645),
            f"{score_info.statistics.count_50}",
            font=Torus_Regular_30,
            anchor="mm",
        )
        draw.text(
            (1445, 645),
            f"{score_info.statistics.count_miss}",
            font=Torus_Regular_30,
            anchor="mm",
        )
    user_icon = await open_user_icon(info)
    gif_frames = []
    if not getattr(user_icon, "is_animated", False):
        icon_bg = user_icon.convert("RGBA").resize((170, 170))
        icon_img = draw_fillet(icon_bg, 15)
        im.alpha_composite(icon_img, (60, 510))
        byt = BytesIO()
        im.save(byt, "png")
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
        gif_bytes, format="gif", save_all=True, append_images=gif_frames[1:]
    )
    # 输出
    gif_frames[0].close()
    user_icon.close()
    return gif_bytes
