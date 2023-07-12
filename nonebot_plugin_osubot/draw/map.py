from datetime import datetime, timedelta
from typing import Union

from PIL import ImageEnhance, ImageDraw
from nonebot.adapters.onebot.v11 import MessageSegment

from ..api import osu_api
from ..schema import Beatmap
from ..mods import calc_mods
from ..file import re_map, get_projectimg, map_downloaded, download_osu
from ..utils import FGM
from ..pp import get_ss_pp
from .utils import calc_songlen, draw_fillet, stars_diff, crop_bg, image2bytesio
from .static import *


async def draw_map_info(mapid: int, mods: list) -> Union[str, MessageSegment]:
    info = await osu_api('map', map_id=mapid)
    if not info:
        return '未查询到该地图信息'
    if isinstance(info, str):
        return info
    mapinfo = Beatmap(**info)
    diffinfo = calc_songlen(mapinfo.total_length), mapinfo.bpm, mapinfo.count_circles, mapinfo.count_sliders
    # 获取地图
    dirpath = await map_downloaded(str(mapinfo.beatmapset_id))
    if not dirpath.exists():
        await download_osu(mapinfo.beatmapset_id, mapinfo.id)
    osu = dirpath / f"{mapinfo.id}.osu"
    ss_pp_info = get_ss_pp(str(osu.absolute()), calc_mods(mods))
    # 计算时间
    if mapinfo.beatmapset.ranked_date:
        old_time = datetime.strptime(mapinfo.beatmapset.ranked_date.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
        new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    else:
        new_time = '谱面状态可能非ranked'
    # BG做地图
    im = Image.new('RGBA', (1200, 600))
    draw = ImageDraw.Draw(im)
    cover = re_map(osu)
    cover_crop = await crop_bg('MB', dirpath / cover)
    cover_img = ImageEnhance.Brightness(cover_crop).enhance(2 / 4.0)
    im.alpha_composite(cover_img)
    # 获取地图info
    im.alpha_composite(MapBg)
    # 模式
    mode_bg = stars_diff(FGM[mapinfo.mode], ss_pp_info.difficulty.stars)
    mode_img = mode_bg.resize((50, 50))
    im.alpha_composite(mode_img, (50, 100))
    # cs - diff
    mapdiff = [mapinfo.cs, mapinfo.drain, mapinfo.accuracy, mapinfo.ar, ss_pp_info.difficulty.stars]
    for num, i in enumerate(mapdiff):
        color = (255, 255, 255, 255)
        if num == 4:
            color = (255, 204, 34, 255)
        difflen = int(250 * i / 10) if i <= 10 else 250
        diff_len = Image.new('RGBA', (difflen, 8), color)
        im.alpha_composite(diff_len, (890, 426 + 35 * num))
        draw.text((1170, 426 + 35 * num), "%.1f" % i, font=Torus_SemiBold_20, anchor='mm')
    # mapper
    icon_url = f'https://a.ppy.sh/{mapinfo.user_id}'
    user_icon = await get_projectimg(icon_url)
    icon = Image.open(user_icon).convert('RGBA').resize((100, 100))
    icon_img = draw_fillet(icon, 10)
    im.alpha_composite(icon_img, (50, 400))
    # mapid
    draw.text((800, 40), f'Setid: {mapinfo.beatmapset_id}  |  Mapid: {mapid}', font=Torus_Regular_20, anchor='lm')
    # 版本
    draw.text((120, 125), mapinfo.version, font=Torus_SemiBold_25, anchor='lm')
    # 曲名
    draw.text((50, 170), mapinfo.beatmapset.title, font=Torus_SemiBold_30, anchor='lt')
    # 曲师
    draw.text((50, 210), f'by {mapinfo.beatmapset.artist_unicode}', font=Torus_SemiBold_25, anchor='lt')
    # 来源
    draw.text((50, 260), f'Source:{mapinfo.beatmapset.source}', font=Torus_SemiBold_25, anchor='lt')
    # mapper
    draw.text((160, 400), '谱师:', font=Torus_SemiBold_20, anchor='lt')
    draw.text((160, 425), mapinfo.beatmapset.creator, font=Torus_SemiBold_20, anchor='lt')
    # ranked时间
    draw.text((160, 460), '上架时间:', font=Torus_SemiBold_20, anchor='lt')
    draw.text((160, 485), new_time, font=Torus_SemiBold_20, anchor='lt')
    # 状态
    draw.text((1100, 304), mapinfo.status.capitalize(), font=Torus_SemiBold_20, anchor='mm')
    # 时长 - 滑条
    for num, i in enumerate(diffinfo):
        draw.text((770 + 120 * num, 365), f'{i}', font=Torus_Regular_20, anchor='lm', fill=(255, 204, 34, 255))
    # maxcb
    draw.text((50, 570), f'最大连击: {mapinfo.max_combo}', font=Torus_SemiBold_20, anchor='lm')
    # pp
    draw.text((320, 570), f'SS PP: {int(round(ss_pp_info.pp, 0))}', font=Torus_SemiBold_20, anchor='lm')
    # 输出
    base = image2bytesio(im)
    im.close()
    msg = MessageSegment.image(base)
    return msg
