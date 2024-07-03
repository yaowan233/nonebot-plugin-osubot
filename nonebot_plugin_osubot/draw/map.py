from datetime import datetime, timedelta
from io import BytesIO
from typing import Union

from PIL import ImageEnhance, ImageDraw

from .static import (
    Image,
    Torus_Regular_20,
    Torus_SemiBold_20,
    MapBg1,
    MapBg,
    IconLs,
    Torus_SemiBold_25,
    osufile,
    extra_30,
)
from .utils import calc_songlen, draw_fillet, stars_diff, crop_bg, is_close
from ..api import osu_api
from ..beatmap_stats_moder import with_mods
from ..file import get_projectimg, download_osu, map_path
from ..info import get_bg
from ..mods import calc_mods
from ..pp import get_ss_pp
from ..schema import Beatmap
from ..schema.score import Mod
from ..utils import FGM


async def draw_map_info(mapid: int, mods: list[str]) -> Union[str, BytesIO]:
    info = await osu_api("map", map_id=mapid)
    if not info:
        return "未查询到该地图信息"
    if isinstance(info, str):
        return info
    mapinfo = Beatmap(**info)
    original_mapinfo = mapinfo.copy()
    mods = [Mod(acronym=mod) for mod in mods]
    mapinfo = with_mods(mapinfo, None, mods)
    diffinfo = (
        calc_songlen(mapinfo.total_length),
        f"{mapinfo.bpm:.1f}",
        mapinfo.count_circles,
        mapinfo.count_sliders,
    )
    # 获取地图
    path = map_path / str(mapinfo.beatmapset_id)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(mapinfo.beatmapset_id, mapid)
    ss_pp_info = get_ss_pp(str(osu.absolute()), calc_mods(mods))
    original_ss_pp_info = get_ss_pp(str(osu.absolute()), 0)
    # 计算时间
    if mapinfo.beatmapset.ranked_date:
        old_time = datetime.strptime(mapinfo.beatmapset.ranked_date.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        new_time = (old_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        new_time = "谱面状态非上架"
    # BG做地图
    im = Image.new("RGBA", (1200, 600))
    draw = ImageDraw.Draw(im)
    bg = await get_bg(mapinfo.id, mapinfo.beatmapset_id)
    cover_crop = await crop_bg((1200, 600), bg)
    cover_img = ImageEnhance.Brightness(cover_crop).enhance(2 / 4.0)
    im.alpha_composite(cover_img)
    # 获取地图info
    if FGM[mapinfo.mode] == 3:
        im.alpha_composite(MapBg1)
    else:
        im.alpha_composite(MapBg)
    # 模式
    draw.text((50, 65), IconLs[FGM[mapinfo.mode]], font=extra_30, anchor="lt")
    # 难度星星
    stars_bg = stars_diff(ss_pp_info.difficulty.stars)
    stars_img = stars_bg.resize((80, 30))
    im.alpha_composite(stars_img, (90, 65))
    if ss_pp_info.difficulty.stars < 6.5:
        color = (0, 0, 0, 255)
    else:
        color = (255, 217, 102, 255)
    # 星级
    draw.text(
        (100, 78),
        f"★{ss_pp_info.difficulty.stars:.2f}",
        font=Torus_SemiBold_20,
        anchor="lm",
        fill=color,
    )
    # cs, ar, od, hp
    mapdiff = [mapinfo.cs, mapinfo.drain, mapinfo.accuracy, mapinfo.ar]
    original_mapdiff = [
        original_mapinfo.cs,
        original_mapinfo.drain,
        original_mapinfo.accuracy,
        original_mapinfo.ar,
    ]

    for num, (original, new) in enumerate(zip(original_mapdiff, mapdiff)):
        if is_close(new, original):
            color = (255, 255, 255, 255)
            orig_difflen = int(250 * max(0, original) / 10) if original <= 10 else 250
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), color)
            im.alpha_composite(orig_diff_len, (890, 426 + 35 * num))
        elif new > original:
            color = (198, 92, 102, 255)
            orig_color = (246, 136, 144, 255)
            new_difflen = int(250 * max(0, new) / 10) if new <= 10 else 250
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (890, 426 + 35 * num))
            orig_difflen = int(250 * max(0, original) / 10) if original <= 10 else 250
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (890, 426 + 35 * num))
        elif new < original:
            color = (161, 212, 238, 255)
            orig_color = (255, 255, 255, 255)
            orig_difflen = int(250 * max(0, original) / 10) if original <= 10 else 250
            orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
            im.alpha_composite(orig_diff_len, (890, 426 + 35 * num))
            new_difflen = int(250 * max(0, new) / 10) if new <= 10 else 250
            new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
            im.alpha_composite(new_diff_len, (890, 426 + 35 * num))
        else:
            raise Exception("没有这种情况")
        draw.text(
            (1170, 428 + 35 * num),
            str(float(f"{new:.2f}")).rstrip("0").rstrip("."),
            font=Torus_SemiBold_20,
            anchor="mm",
        )
    # stardiff
    stars = ss_pp_info.difficulty.stars
    original_stars = original_ss_pp_info.difficulty.stars
    if stars > original_stars:
        color = (198, 92, 102, 255)
        orig_color = (246, 111, 34, 255)
        new_difflen = int(250 * max(0.0, stars) / 10) if stars <= 10 else 250
        new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
        im.alpha_composite(new_diff_len, (890, 566))
        orig_difflen = int(250 * max(0.0, original_stars) / 10) if original_stars <= 10 else 250
        orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
        im.alpha_composite(orig_diff_len, (890, 566))
    elif stars < original_stars:
        color = (161, 187, 127, 255)
        orig_color = (255, 204, 34, 255)
        orig_difflen = int(250 * max(0.0, original_stars) / 10) if original_stars <= 10 else 250
        orig_diff_len = Image.new("RGBA", (orig_difflen, 8), orig_color)
        im.alpha_composite(orig_diff_len, (890, 566))
        new_difflen = int(250 * max(0.0, stars) / 10) if stars <= 10 else 250
        new_diff_len = Image.new("RGBA", (new_difflen, 8), color)
        im.alpha_composite(new_diff_len, (890, 566))
    else:
        color = (255, 204, 34, 255)
        difflen = int(250 * stars / 10) if stars <= 10 else 250
        diff_len = Image.new("RGBA", (difflen, 8), color)
        im.alpha_composite(diff_len, (890, 566))
    draw.text((1170, 566), f"{stars:.2f}", font=Torus_SemiBold_20, anchor="mm")
    # 绘制mods
    if mods:
        for mods_num, s_mods in enumerate(mods):
            mods_bg = osufile / "mods" / f"{s_mods.acronym}.png"
            mods_img = Image.open(mods_bg).convert("RGBA")
            im.alpha_composite(mods_img, (700 + 50 * mods_num, 295))
    # mapper
    icon_url = f"https://a.ppy.sh/{mapinfo.user_id}"
    user_icon = await get_projectimg(icon_url)
    icon = Image.open(user_icon).convert("RGBA").resize((100, 100))
    icon_img = draw_fillet(icon, 10)
    im.alpha_composite(icon_img, (50, 400))
    # mapid
    draw.text(
        (1190, 80),
        f"Setid: {mapinfo.beatmapset_id} | Mapid: {mapid}",
        font=Torus_Regular_20,
        anchor="rm",
    )
    # 难度名
    version = mapinfo.version
    max_version_length = 60
    if len(version) > max_version_length:
        version = version[: max_version_length - 3] + "..."
    text = f"{version}"
    draw.text((180, 78), text, font=Torus_SemiBold_20, anchor="lm")
    # 曲名+曲师
    text = f"{mapinfo.beatmapset.title} | by {mapinfo.beatmapset.artist_unicode}"
    max_length = 80
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."

    draw.text((50, 37), text, font=Torus_SemiBold_25, anchor="lm")
    # 来源
    # draw.text((50, 260), f"Source:{mapinfo.beatmapset.source}", font=Torus_SemiBold_25, anchor="rt")
    # mapper
    draw.text((160, 400), "谱师:", font=Torus_SemiBold_20, anchor="lt")
    draw.text((160, 425), mapinfo.beatmapset.creator, font=Torus_SemiBold_20, anchor="lt")
    # ranked时间
    draw.text((160, 460), "上架时间:", font=Torus_SemiBold_20, anchor="lt")
    draw.text((160, 485), new_time, font=Torus_SemiBold_20, anchor="lt")
    # 状态
    draw.text((1100, 304), mapinfo.status.capitalize(), font=Torus_SemiBold_20, anchor="mm")
    # 时长 - 滑条
    for num, i in enumerate(diffinfo):
        draw.text(
            (770 + 120 * num, 365),
            f"{i}",
            font=Torus_Regular_20,
            anchor="lm",
            fill=(255, 204, 34, 255),
        )
    # maxcb
    draw.text((50, 570), f"最大连击: {mapinfo.max_combo}", font=Torus_SemiBold_20, anchor="lm")
    # pp
    draw.text(
        (320, 570),
        f"SS PP: {int(round(ss_pp_info.pp, 0))}",
        font=Torus_SemiBold_20,
        anchor="lm",
    )
    # 输出
    byt = BytesIO()
    im.convert("RGB").save(byt, "jpeg")
    im.close()
    return byt
