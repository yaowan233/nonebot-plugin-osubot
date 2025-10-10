from io import BytesIO
from datetime import datetime, timedelta

from PIL import ImageDraw, ImageFilter, ImageEnhance

from ..file import get_projectimg
from ..api import get_beatmapsets_info
from .utils import crop_bg, stars_diff, calc_songlen
from .static import Image, BarImg, IconLs, Torus_SemiBold_20, Torus_SemiBold_40, Torus_SemiBold_50, extra_30, Stars


async def draw_bmap_info(mapid) -> BytesIO:
    data = await get_beatmapsets_info(mapid)
    coverurl = f"https://assets.ppy.sh/beatmaps/{mapid}/covers/cover@2x.jpg"
    cover = await get_projectimg(coverurl)
    # 新建
    if len(data.beatmaps) > 20:
        im_h = 400 + 102 * 20
    else:
        im_h = 400 + 102 * (len(data.beatmaps) - 1)
    im = Image.new("RGBA", (1200, im_h), (31, 41, 46, 255))
    draw = ImageDraw.Draw(im)
    # 背景
    cover_crop = await crop_bg((1200, 300), cover)
    cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(1))
    cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
    im.alpha_composite(cover_img, (0, 0))
    # 曲名
    draw.text((25, 15), data.title, font=Torus_SemiBold_40, anchor="lt")
    # 曲师
    draw.text((25, 70), f"by {data.artist}", font=Torus_SemiBold_20, anchor="lt")
    # mapper
    draw.text((25, 105), f"谱面作者: {data.creator}", font=Torus_SemiBold_20, anchor="lt")
    # rank时间
    if not data.ranked_date:
        approved_date = "谱面状态可能非ranked"
    else:
        datearray = datetime.fromisoformat(data.ranked_date.replace("Z", ""))
        approved_date = (datearray + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    draw.text((25, 140), f"上架时间: {approved_date}", font=Torus_SemiBold_20, anchor="lt")
    # 来源
    if data.source:
        draw.text((25, 175), f"Source: {data.source}", font=Torus_SemiBold_20, anchor="lt")
    # bpm
    draw.text((1150, 105), f"BPM: {data.bpm}", font=Torus_SemiBold_20, anchor="rt")
    # 曲长
    music_len = calc_songlen(data.beatmaps[0].total_length)
    draw.text((1150, 140), f"length: {music_len}", font=Torus_SemiBold_20, anchor="rt")
    # Setid
    draw.text((1150, 35), f"Setid: {mapid}", font=Torus_SemiBold_20, anchor="rt")
    gmap = sorted(data.beatmaps, key=lambda k: k.difficulty_rating, reverse=False)
    for num, cmap in enumerate(gmap):
        if num < 20:
            h_num = 102 * num
            # 难度
            draw.text((20, 320 + h_num), IconLs[cmap.mode_int], font=extra_30, anchor="lt")
            # 星星
            stars_bg = stars_diff(cmap.difficulty_rating, Stars)
            stars_img = stars_bg.resize((80, 30))
            im.alpha_composite(stars_img, (60, 320 + h_num))
            # diff
            im.alpha_composite(BarImg, (10, 365 + h_num))
            gc = ["CS", "HP", "OD", "AR"]
            for index, i in enumerate((cmap.cs, cmap.drain, cmap.accuracy, cmap.ar)):
                diff_len = int(200 * i / 10) if i <= 10 else 200
                diff_bg = Image.new("RGBA", (diff_len, 12), (255, 255, 255, 255))
                im.alpha_composite(diff_bg, (50 + 300 * index, 365 + h_num))
                draw.text(
                    (20 + 300 * index, 369 + h_num),
                    gc[index],
                    font=Torus_SemiBold_20,
                    anchor="lm",
                )
                draw.text(
                    (265 + 300 * index, 369 + h_num),
                    f"{i}",
                    font=Torus_SemiBold_20,
                    anchor="lm",
                    fill=(255, 204, 34, 255),
                )
                if index != 3:
                    draw.text(
                        (300 + 300 * index, 369 + h_num),
                        "|",
                        font=Torus_SemiBold_20,
                        anchor="lm",
                    )
            # 难度
            if cmap.difficulty_rating < 6.5:
                color = (0, 0, 0, 255)
            else:
                color = (255, 217, 102, 255)
            draw.text(
                (65, 335 + h_num), f"★{cmap.difficulty_rating:.2f}", font=Torus_SemiBold_20, anchor="lm", fill=color
            )
            # version
            draw.text(
                (150, 335 + h_num),
                f"{cmap.version}",
                font=Torus_SemiBold_20,
                anchor="lm",
            )
            # mapid
            draw.text(
                (1150, 328 + h_num),
                f"Mapid: {cmap.id}",
                font=Torus_SemiBold_20,
                anchor="rm",
            )
            # maxcb
            draw.text(
                (700, 328 + h_num),
                f"Max Combo: {cmap.max_combo or 0}",
                font=Torus_SemiBold_20,
                anchor="lm",
            )
            # 分割线
            div = Image.new("RGBA", (1150, 2), (46, 53, 56, 255)).convert("RGBA")
            im.alpha_composite(div, (25, 400 + h_num))
        else:
            plusnum = f"+ {num - 19}"
            draw.text((600, 350 + 102 * 20), plusnum, font=Torus_SemiBold_50, anchor="mm")
    byt = BytesIO()
    im.convert("RGB").save(byt, "jpeg")
    im.close()
    return byt
