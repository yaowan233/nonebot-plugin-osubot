from datetime import datetime, timedelta
from io import BytesIO
from typing import Union

from PIL import ImageEnhance, ImageDraw

from ..api import osu_api, get_map_bg
from ..schema import Beatmap
from ..mods import calc_mods
from ..file import re_map, get_projectimg, download_osu, map_path
from ..utils import FGM
from ..pp import get_ss_pp
from .utils import calc_songlen, draw_fillet, stars_diff, crop_bg, image2bytesio
from .static import *


async def draw_map_info(mapid: int, mods: list) -> Union[str, BytesIO]:
    info = await osu_api("map", map_id=mapid)
    if not info:
        return "未查询到该地图信息"
    if isinstance(info, str):
        return info
    mapinfo = Beatmap(**info)
    diffinfo = (
        calc_songlen(mapinfo.total_length),
        mapinfo.bpm,
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
    # 计算时间
    if mapinfo.beatmapset.ranked_date:
        old_time = datetime.strptime(
            mapinfo.beatmapset.ranked_date.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"
        )
        new_time = (old_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        new_time = "谱面状态非上架"
    # BG做地图
    im = Image.new("RGBA", (1200, 600))
    draw = ImageDraw.Draw(im)
    cover = re_map(osu)
    cover_path = path / cover
    if not cover_path.exists():
        if bg := await get_map_bg(mapid, mapinfo.beatmapset_id, cover):
            with open(cover_path, "wb") as f:
                f.write(bg.getvalue())
    cover_crop = await crop_bg("MB", cover_path)
    cover_img = ImageEnhance.Brightness(cover_crop).enhance(2 / 4.0)
    im.alpha_composite(cover_img)
    # 获取地图info
    if FGM[mapinfo.mode] == 3:
        im.alpha_composite(MapBg1)
    else:
        im.alpha_composite(MapBg)
    # 模式
    mode_bg = stars_diff(FGM[mapinfo.mode], ss_pp_info.difficulty.stars)
    mode_img = mode_bg.resize((25, 25))
    im.alpha_composite(mode_img, (5, 65))
    # cs, ar, od, hp
    mapdiff = [
        mapinfo.cs,
        mapinfo.drain,
        mapinfo.accuracy,
        mapinfo.ar,
    ]
    for num, i in enumerate(mapdiff):
        color = (255, 255, 255, 255)
        if num == 4:
            color = (255, 204, 34, 255)
        difflen = int(250 * i / 10) if i <= 10 else 250
        diff_len = Image.new("RGBA", (difflen, 8), color)
        im.alpha_composite(diff_len, (890, 426 + 35 * num))
        if i == round(i):
            draw.text(
                (1170, 428 + 35 * num), "%.0f" % i, font=Torus_SemiBold_20, anchor="mm"
            )
        else:
            draw.text(
                (1170, 428 + 35 * num), "%.1f" % i, font=Torus_SemiBold_20, anchor="mm"
            )
    # stardiff
    i = ss_pp_info.difficulty.stars
    color = (255, 204, 34, 255)
    difflen = int(250 * i / 10) if i <= 10 else 250
    diff_len = Image.new('RGBA', (difflen, 8), color)
    im.alpha_composite(diff_len, (890, 566))
    draw.text((1470, 450), f'{i:.2f}', font=Torus_SemiBold_20, anchor='mm')
    # 绘制mods
    if mods:
        for mods_num, s_mods in enumerate(mods):
            mods_bg = osufile / 'mods' / f'{s_mods}.png'
            mods_img = Image.open(mods_bg).convert('RGBA')
            im.alpha_composite(mods_img, (700 + 50 * mods_num, 295))
    # mapper
    icon_url = f"https://a.ppy.sh/{mapinfo.user_id}"
    user_icon = await get_projectimg(icon_url)
    icon = Image.open(user_icon).convert("RGBA").resize((100, 100))
    icon_img = draw_fillet(icon, 10)
    im.alpha_composite(icon_img, (50, 400))
    # mapid
    draw.text(
        (1190, 40),
        f"Setid: {mapinfo.beatmapset_id}  |  Mapid: {mapid}",
        font=Torus_Regular_20,
        anchor="rm",
    )
    # 难度名
    version = mapinfo.version
    max_version_length = 60
    if len(version) > max_version_length:
        version = version[:max_version_length - 3] + '...'
    text = f'{version}'
    draw.text((40, 75), text, font=Torus_SemiBold_20, anchor='lm')
    # 曲名+曲师
    text = f'{mapinfo.beatmapset.title} | by {mapinfo.beatmapset.artist_unicode}'
    max_length = 80
    if len(text) > max_length:
        text = text[:max_length-3] + '...'

    draw.text((5, 38), text, font=Torus_SemiBold_20, anchor='lm')
    # 来源
    #draw.text((50, 260), f'Source:{mapinfo.beatmapset.source}', font=Torus_SemiBold_25, anchor='rt')
    # mapper
    draw.text((160, 400), "谱师:", font=Torus_SemiBold_20, anchor="lt")
    draw.text(
        (160, 425), mapinfo.beatmapset.creator, font=Torus_SemiBold_20, anchor="lt"
    )
    # ranked时间
    draw.text((160, 460), "上架时间:", font=Torus_SemiBold_20, anchor="lt")
    draw.text((160, 485), new_time, font=Torus_SemiBold_20, anchor="lt")
    # 状态
    draw.text(
        (1100, 304), mapinfo.status.capitalize(), font=Torus_SemiBold_20, anchor="mm"
    )
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
    draw.text(
        (50, 570), f"最大连击: {mapinfo.max_combo}", font=Torus_SemiBold_20, anchor="lm"
    )
    # pp
    draw.text(
        (320, 570),
        f"SS PP: {int(round(ss_pp_info.pp, 0))}",
        font=Torus_SemiBold_20,
        anchor="lm",
    )
    # 输出
    base = image2bytesio(im)
    im.close()
    return base
