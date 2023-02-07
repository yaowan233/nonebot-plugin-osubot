from datetime import datetime, timedelta
from typing import Union

from PIL import ImageEnhance
from nonebot.adapters.onebot.v11 import MessageSegment

from ..api import osu_api
from ..schema import Beatmap
from ..mods import calc_mods
from ..file import re_map, get_projectimg, map_downloaded, download_osu
from ..utils import FGM
from ..pp import get_ss_pp
from .utils import calc_songlen, DataText, draw_text, draw_fillet, stars_diff, crop_bg, image2bytesio
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
    cover = re_map(osu)
    cover_crop = crop_bg('MB', dirpath / cover)
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
        w_diff = DataText(1170, 426 + 35 * num, 20, "%.1f" % i, Torus_SemiBold, anchor='mm')
        im = draw_text(im, w_diff)
    # mapper
    icon_url = f'https://a.ppy.sh/{mapinfo.user_id}'
    user_icon = await get_projectimg(icon_url)
    icon = Image.open(user_icon).convert('RGBA').resize((100, 100))
    icon_img = draw_fillet(icon, 10)
    im.alpha_composite(icon_img, (50, 400))
    # mapid
    w_mapid = DataText(800, 40, 22, f'Setid: {mapinfo.beatmapset_id}  |  Mapid: {mapid}', Torus_Regular, anchor='lm')
    im = draw_text(im, w_mapid)
    # 版本
    w_version = DataText(120, 125, 25, mapinfo.version, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_version)
    # 曲名
    w_title = DataText(50, 170, 30, mapinfo.beatmapset.title, Torus_SemiBold)
    im = draw_text(im, w_title)
    # 曲师
    w_artist = DataText(50, 210, 25, f'by {mapinfo.beatmapset.artist_unicode}', Torus_SemiBold)
    im = draw_text(im, w_artist)
    # 来源
    w_source = DataText(50, 260, 25, f'Source:{mapinfo.beatmapset.source}', Torus_SemiBold)
    im = draw_text(im, w_source)
    # mapper
    w_mapper_by = DataText(160, 400, 20, '谱师:', Torus_SemiBold)
    im = draw_text(im, w_mapper_by)
    w_mapper = DataText(160, 425, 20, mapinfo.beatmapset.creator, Torus_SemiBold)
    im = draw_text(im, w_mapper)
    # ranked时间
    w_time_by = DataText(160, 460, 20, '上架时间:', Torus_SemiBold)
    im = draw_text(im, w_time_by)
    w_time = DataText(160, 485, 20, new_time, Torus_SemiBold)
    im = draw_text(im, w_time)
    # 状态
    w_status = DataText(1100, 304, 20, mapinfo.status.capitalize(), Torus_SemiBold, anchor='mm')
    im = draw_text(im, w_status)
    # 时长 - 滑条
    for num, i in enumerate(diffinfo):
        w_info = DataText(770 + 120 * num, 365, 20, i, Torus_Regular, anchor='lm')
        im = draw_text(im, w_info, (255, 204, 34, 255))
    # maxcb
    w_mapcb = DataText(50, 570, 20, f'最大连击: {mapinfo.max_combo}', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_mapcb)
    # pp
    w_pp = DataText(320, 570, 20, f'SS PP: {int(round(ss_pp_info.pp, 0))}', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_pp)
    # 输出
    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg
