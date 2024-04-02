from datetime import datetime, timedelta
from io import BytesIO
from typing import Union

from PIL import ImageFilter, ImageEnhance, ImageDraw

from ..api import osu_api, sayo_api
from ..schema import SayoBeatmap
from ..file import get_projectimg
from .static import *
from .utils import crop_bg, calc_songlen, stars_diff, image2bytesio
from ..utils import GM


async def draw_bmap_info(mapid, op: bool = False) -> Union[str, BytesIO]:
    if op:
        info = await osu_api("map", map_id=mapid)
        if not info:
            return "未查询到地图"
        elif isinstance(info, str):
            return info
        mapid = info["beatmapset_id"]
    info = await sayo_api(mapid)
    if isinstance(info, str):
        return info
    sayo_info = SayoBeatmap(**info)
    if sayo_info.status == -1:
        return "在sayobot未查询到该地图"
    data = sayo_info.data

    coverurl = f"https://assets.ppy.sh/beatmaps/{mapid}/covers/cover@2x.jpg"
    cover = await get_projectimg(coverurl)
    # 新建
    if len(data.bid_data) > 20:
        im_h = 400 + 102 * 20
    else:
        im_h = 400 + 102 * (len(data.bid_data) - 1)
    im = Image.new("RGBA", (1200, im_h), (31, 41, 46, 255))
    draw = ImageDraw.Draw(im)
    # 背景
    cover_crop = await crop_bg("MP", cover)
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
    if data.approved_date == -1:
        approved_date = "谱面状态可能非ranked"
    else:
        datearray = datetime.utcfromtimestamp(data.approved_date)
        approved_date = (datearray + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    draw.text((25, 140), f"上架时间: {approved_date}", font=Torus_SemiBold_20, anchor="lt")
    # 来源
    draw.text((25, 175), f"Source: {data.source}", font=Torus_SemiBold_20, anchor="lt")
    # bpm
    draw.text((1150, 105), f"BPM: {data.bpm}", font=Torus_SemiBold_20, anchor="rt")
    # 曲长
    music_len = calc_songlen(data.bid_data[0].length)
    draw.text((1150, 140), f"length: {music_len}", font=Torus_SemiBold_20, anchor="rt")
    # Setid
    draw.text((1150, 35), f"Setid: {mapid}", font=Torus_SemiBold_20, anchor="rt")
    gmap = sorted(data.bid_data, key=lambda k: k.star, reverse=False)
    for num, cmap in enumerate(gmap):
        if num < 20:
            h_num = 102 * num
            # 难度
            draw.text((20, 320 + h_num), IconLs[GM[cmap.mode]], font=extra_30, anchor="lt")
            # 星星
            stars_bg = stars_diff(cmap.star)
            stars_img = stars_bg.resize((80, 30))
            im.alpha_composite(stars_img, (60, 320 + h_num))
            # diff
            im.alpha_composite(BarImg, (10, 365 + h_num))
            gc = ["CS", "HP", "OD", "AR"]
            for index, i in enumerate((cmap.CS, cmap.HP, cmap.OD, cmap.AR)):
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
            if cmap.star < 6.5:
                color = (0, 0, 0, 255)
            else:
                color = (255, 217, 102, 255)
            draw.text(
                (65, 335 + h_num),
                f"★{cmap.star:.2f}",
                font=Torus_SemiBold_20,
                anchor="lm",
                fill=color
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
                f"Mapid: {cmap.bid}",
                font=Torus_SemiBold_20,
                anchor="rm",
            )
            # maxcb
            draw.text(
                (700, 328 + h_num),
                f"Max Combo: {cmap.maxcombo}",
                font=Torus_SemiBold_20,
                anchor="lm",
            )
            # 分割线
            div = Image.new("RGBA", (1150, 2), (46, 53, 56, 255)).convert("RGBA")
            im.alpha_composite(div, (25, 400 + h_num))
        else:
            plusnum = f"+ {num - 19}"
            draw.text(
                (600, 350 + 102 * 20), plusnum, font=Torus_SemiBold_50, anchor="mm"
            )
    base = image2bytesio(im)
    im.close()
    return base
