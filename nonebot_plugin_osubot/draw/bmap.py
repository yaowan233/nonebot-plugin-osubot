from datetime import datetime, timedelta
from typing import Union

from PIL import ImageFilter, ImageEnhance
from nonebot.adapters.onebot.v11 import MessageSegment

from ..api import osu_api, sayo_api
from ..schema import SayoBeatmap
from ..file import get_projectimg
from .static import *
from .utils import crop_bg, DataText, draw_text, calc_songlen, stars_diff, image2bytesio


async def draw_bmap_info(mapid, op: bool = False) -> Union[str, MessageSegment]:
    if op:
        info = await osu_api('map', map_id=mapid)
        if not info:
            return '未查询到地图'
        elif isinstance(info, str):
            return info
        mapid = info['beatmapset_id']
    info = await sayo_api(mapid)
    if isinstance(info, str):
        return info
    sayo_info = SayoBeatmap(**info)
    if sayo_info.status == -1:
        return '在sayobot未查询到该地图'
    data = sayo_info.data

    coverurl = f'https://assets.ppy.sh/beatmaps/{mapid}/covers/cover@2x.jpg'
    cover = await get_projectimg(coverurl)
    # 新建
    if len(data.bid_data) > 20:
        im_h = 400 + 102 * 20
    else:
        im_h = 400 + 102 * (len(data.bid_data) - 1)
    im = Image.new('RGBA', (1200, im_h), (31, 41, 46, 255))
    # 背景
    cover_crop = crop_bg('MP', cover)
    cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(1))
    cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
    im.alpha_composite(cover_img, (0, 0))
    # 曲名
    w_title = DataText(25, 40, 38, data.title, Torus_SemiBold)
    im = draw_text(im, w_title)
    # 曲师
    w_artist = DataText(25, 75, 20, f'by {data.artist}', Torus_SemiBold)
    im = draw_text(im, w_artist)
    # mapper
    w_mapper = DataText(25, 110, 20, f'谱面作者: {data.creator}', Torus_SemiBold)
    im = draw_text(im, w_mapper)
    # rank时间
    if data.approved_date == -1:
        approved_date = '谱面状态可能非ranked'
    else:
        datearray = datetime.utcfromtimestamp(data.approved_date)
        approved_date = (datearray + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    w_apptime = DataText(25, 145, 20, f'上架时间: {approved_date}', Torus_SemiBold)
    im = draw_text(im, w_apptime)
    # 来源
    w_source = DataText(25, 180, 20, f'Source: {data.source}', Torus_SemiBold)
    im = draw_text(im, w_source)
    # bpm
    w_bpm = DataText(1150, 110, 20, f'BPM: {data.bpm}', Torus_SemiBold, anchor='rt')
    im = draw_text(im, w_bpm)
    # 曲长
    music_len = calc_songlen(data.bid_data[0].length)
    w_music_len = DataText(1150, 145, 20, f'lenght: {music_len}', Torus_SemiBold, anchor='rt')
    im = draw_text(im, w_music_len)
    # Setid
    w_setid = DataText(1150, 20, 20, f'Setid: {mapid}', Torus_SemiBold, anchor='rt')
    im = draw_text(im, w_setid)
    gmap = sorted(data.bid_data, key=lambda k: k.star, reverse=False)
    for num, cmap in enumerate(gmap):
        if num < 20:
            h_num = 102 * num
            # 难度
            mode_bg = stars_diff(cmap.mode, cmap.star)
            mode_img = mode_bg.resize((20, 20))
            im.alpha_composite(mode_img, (20, 320 + h_num))
            # 星星
            stars_bg = stars_diff('stars', cmap.star)
            stars_img = stars_bg.resize((20, 20))
            im.alpha_composite(stars_img, (50, 320 + h_num))
            # diff
            im.alpha_composite(BarImg, (10, 365 + h_num))
            gc = ['CS', 'HP', 'OD', 'AR']
            for index, i in enumerate((cmap.CS, cmap.HP, cmap.OD, cmap.AR)):
                diff_len = int(200 * i / 10) if i <= 10 else 200
                diff_bg = Image.new('RGBA', (diff_len, 12), (255, 255, 255, 255))
                im.alpha_composite(diff_bg, (50 + 300 * index, 365 + h_num))
                w_d_name = DataText(20 + 300 * index, 369 + h_num, 20, gc[index], Torus_SemiBold, anchor='lm')
                im = draw_text(im, w_d_name)
                w_diff = DataText(265 + 300 * index, 369 + h_num, 20, i, Torus_SemiBold, anchor='lm')
                im = draw_text(im, w_diff, (255, 204, 34, 255))
                if index != 3:
                    w_d = DataText(300 + 300 * index, 369 + h_num, 20, '|', Torus_SemiBold, anchor='lm')
                    im = draw_text(im, w_d)
            # 难度
            w_star = DataText(80, 328 + h_num, 20, f'{cmap.star:.1f}', Torus_SemiBold, anchor='lm')
            im = draw_text(im, w_star)
            # version
            w_version = DataText(125, 328 + h_num, 20, f' |  {cmap.version}', Torus_SemiBold, anchor='lm')
            im = draw_text(im, w_version)
            # mapid
            w_mapid = DataText(1150, 328 + h_num, 20, f'Mapid: {cmap.bid}', Torus_SemiBold, anchor='rm')
            im = draw_text(im, w_mapid)
            # maxcb
            w_maxcb = DataText(700, 328 + h_num, 20, f'Max Combo: {cmap.maxcombo}', Torus_SemiBold, anchor='lm')
            im = draw_text(im, w_maxcb)
            # 分割线
            div = Image.new('RGBA', (1150, 2), (46, 53, 56, 255)).convert('RGBA')
            im.alpha_composite(div, (25, 400 + h_num))
        else:
            plusnum = f'+ {num - 19}'
            w_plusnum = DataText(600, 350 + 102 * 20, 50, plusnum, Torus_SemiBold, anchor='mm')
            im = draw_text(im, w_plusnum)

    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg
