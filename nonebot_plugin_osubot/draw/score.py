import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Union
from PIL import ImageFilter, ImageEnhance
from nonebot.adapters.onebot.v11 import MessageSegment

from ..api import osu_api
from ..schema import Score, Beatmap, User
from ..mods import get_mods_list
from ..file import re_map, get_projectimg, map_downloaded, download_osu, user_cache_path
from ..utils import GMN, FGM
from ..pp import cal_pp, get_if_pp_ss_pp

from .static import *
from .utils import draw_acc, draw_fillet, draw_text, crop_bg, DataText, calc_songlen, stars_diff, image2bytesio,\
    get_modeimage


async def draw_score(project: str,
                     uid: int,
                     mode: str,
                     mods: Optional[List[str]],
                     best: int = 0,
                     mapid: int = 0) -> Union[str, MessageSegment]:
    task0 = asyncio.create_task(osu_api(project, uid, mode, mapid))
    task1 = asyncio.create_task(osu_api('info', uid))
    score_json = await task0
    if not score_json:
        return f'未查询到在 {GMN[mode]} 的游玩记录'
    elif isinstance(score_json, str):
        return score_json
    if project in ('recent', 'pr'):
        score_info = Score(**score_json[0])
        grank = '--'
    elif project == 'bp':
        score_ls = [Score(**i) for i in score_json]
        mods_ls = get_mods_list(score_ls, mods)
        if len(mods_ls) < best:
            return f'未找到开启 {"|".join(mods)} Mods的第{best}个成绩'
        score_info = Score(**score_json[mods_ls[best - 1]])
        grank = '--'
    elif project == 'score':
        score_info = Score(**score_json['score'])
        grank = score_json['position']
    else:
        raise 'Project Error'
    # 从官网获取信息
    task2 = asyncio.create_task(osu_api('map', map_id=score_info.beatmap.id))
    task3 = asyncio.create_task(map_downloaded(str(score_info.beatmap.beatmapset_id)))
    info_json = await task1
    info = User(**info_json)
    path = user_cache_path / str(info.id)
    if not path.exists():
        path.mkdir()
    user_header = user_cache_path / str(info.id) / 'header.png'
    user_icon = user_cache_path / str(info.id) / 'icon.png'
    if not user_header.exists():
        user_header = await get_projectimg(info.cover_url)
        with open(path / 'header.png', 'wb') as f:
            f.write(user_header.getvalue())
    if not user_icon.exists():
        user_icon = await get_projectimg(info.avatar_url)
        with open(path / 'icon.png', 'wb') as f:
            f.write(user_icon.getvalue())
    map_json = await task2
    mapinfo = Beatmap(**map_json)
    # 下载地图
    dirpath = await task3
    osu = dirpath / f"{score_info.beatmap.id}.osu"
    if not osu.exists():
        await download_osu(score_info.beatmap.beatmapset_id, score_info.beatmap.id)
    # pp
    pp_info = cal_pp(score_info, str(osu.absolute()))
    if_pp, ss_pp = get_if_pp_ss_pp(score_info, str(osu.absolute()))
    # 新建图片
    im = Image.new('RGBA', (1500, 720))
    # 获取cover并裁剪，高斯，降低亮度
    cover = re_map(osu)
    if cover == 'mapbg.png':
        cover_path = osufile / 'work' / cover
    else:
        cover_path = dirpath / cover
    cover_crop = crop_bg('BG', cover_path)
    cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(1))
    cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
    im.alpha_composite(cover_img, (0, 0))
    # 获取成绩背景做底图
    bg = get_modeimage(FGM[score_info.mode])
    recent_bg = Image.open(bg).convert('RGBA')
    im.alpha_composite(recent_bg)
    # 模式
    mode_bg = stars_diff(FGM[score_info.mode], pp_info.difficulty.stars)
    mode_img = mode_bg.resize((30, 30))
    im.alpha_composite(mode_img, (75, 74))
    # 难度星星
    stars_bg = stars_diff('stars', pp_info.difficulty.stars)
    stars_img = stars_bg.resize((23, 23))
    im.alpha_composite(stars_img, (134, 78))
    # mods
    if 'HD' in score_info.mods or 'FL' in score_info.mods:
        ranking = ['XH', 'SH', 'A', 'B', 'C', 'D', 'F']
    else:
        ranking = ['X', 'S', 'A', 'B', 'C', 'D', 'F']
    if score_info.mods:
        for mods_num, s_mods in enumerate(score_info.mods):
            mods_bg = osufile / 'mods' / f'{s_mods}.png'
            mods_img = Image.open(mods_bg).convert('RGBA')
            im.alpha_composite(mods_img, (500 + 50 * mods_num, 160))
    # 成绩S-F
    rank_ok = False
    for rank_num, i in enumerate(ranking):
        rank_img = osufile / 'ranking' / f'ranking-{i}.png'
        if rank_ok:
            rank_b = Image.open(rank_img).convert('RGBA').resize((48, 24))
            rank_new = Image.new('RGBA', rank_b.size, (0, 0, 0, 0))
            rank_bg = Image.blend(rank_new, rank_b, 0.5)
        elif i != score_info.rank:
            rank_b = Image.open(rank_img).convert('RGBA').resize((48, 24))
            rank_new = Image.new('RGBA', rank_b.size, (0, 0, 0, 0))
            rank_bg = Image.blend(rank_new, rank_b, 0.2)
        else:
            rank_bg = Image.open(rank_img).convert('RGBA').resize((48, 24))
            rank_ok = True
        im.alpha_composite(rank_bg, (75, 163 + 39 * rank_num))
    # 成绩+acc
    im = draw_acc(im, score_info.accuracy, score_info.mode)
    # 头图
    headericon_crop = crop_bg('H', user_header)
    headericon_gb = headericon_crop.filter(ImageFilter.GaussianBlur(1))
    headericon_img = ImageEnhance.Brightness(headericon_gb).enhance(2 / 4.0)
    headericon_d = draw_fillet(headericon_img, 15)
    im.alpha_composite(headericon_d, (50, 511))
    # 头像
    icon_bg = Image.open(user_icon).convert('RGBA').resize((90, 90))
    icon_img = draw_fillet(icon_bg, 15)
    im.alpha_composite(icon_img, (90, 526))
    # 地区
    country = osufile / 'flags' / f'{score_info.user.country_code}.png'
    country_bg = Image.open(country).convert('RGBA').resize((58, 39))
    im.alpha_composite(country_bg, (195, 526))
    # 在线状态
    status = osufile / 'work' / ('on-line.png' if score_info.user.is_online else 'off-line.png')
    status_bg = Image.open(status).convert('RGBA').resize((45, 45))
    im.alpha_composite(status_bg, (114, 632))
    # supporter
    if score_info.user.is_supporter:
        im.alpha_composite(SupporterBg.resize((40, 40)), (267, 526))
    # cs, ar, od, hp, stardiff
    mapdiff = [mapinfo.cs, mapinfo.drain, mapinfo.accuracy, mapinfo.ar, pp_info.difficulty.stars]
    for num, i in enumerate(mapdiff):
        color = (255, 255, 255, 255)
        if num == 4:
            color = (255, 204, 34, 255)
        diff_len = int(250 * i / 10) if i <= 10 else 250
        diff_len = Image.new('RGBA', (diff_len, 8), color)
        im.alpha_composite(diff_len, (1190, 306 + 35 * num))
        w_diff = DataText(1470, 306 + 35 * num, 20, f'{i:.1f}', Torus_SemiBold, anchor='mm')
        im = draw_text(im, w_diff)
    # 时长 - 滑条
    diff_info = calc_songlen(mapinfo.total_length), mapinfo.bpm, mapinfo.count_circles, mapinfo.count_sliders
    for num, i in enumerate(diff_info):
        w_info = DataText(1070 + 120 * num, 245, 20, i, Torus_Regular, anchor='lm')
        im = draw_text(im, w_info, (255, 204, 34, 255))
    # 状态
    w_status = DataText(1400, 184, 20, mapinfo.status.capitalize(), Torus_SemiBold, anchor='mm')
    im = draw_text(im, w_status)
    # mapid
    w_mapid = DataText(1425, 89, 27, f'Setid: {score_info.beatmap.beatmapset_id}  |  Mapid: {score_info.beatmap.id}',
                       Torus_SemiBold, anchor='rm')
    im = draw_text(im, w_mapid)
    # 曲名
    w_title = DataText(75, 38, 30, f'{mapinfo.beatmapset.title} | by {mapinfo.beatmapset.artist_unicode}',
                       Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_title)
    # 星级
    w_diff = DataText(162, 89, 18, f'{pp_info.difficulty.stars:.1f}', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_diff)
    # 谱面版本，mapper
    w_version = DataText(225, 89, 22, f'{mapinfo.version} | 谱师: {mapinfo.beatmapset.creator}', Torus_SemiBold,
                         anchor='lm')
    im = draw_text(im, w_version)
    # 评价
    w_rank = DataText(316, 307, 75, score_info.rank, Venera, anchor='mm')
    im = draw_text(im, w_rank)
    # 分数
    w_score = DataText(498, 251, 75, f'{score_info.score:,}', Torus_Regular, anchor='lm')
    im = draw_text(im, w_score)
    # 玩家
    w_played = DataText(498, 316, 18, '玩家:', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_played)
    w_username = DataText(630, 316, 18, score_info.user.username, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_username)
    # 时间
    w_date = DataText(498, 341, 18, '达成时间:', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_date)
    old_time = datetime.strptime(score_info.created_at.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
    new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    w_time = DataText(630, 341, 18, new_time, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_time)
    # 全球排名
    w_grank = DataText(583, 410, 24, grank, Torus_SemiBold, anchor='mm')
    im = draw_text(im, w_grank)
    # 左下玩家名
    w_l_username = DataText(195, 590, 24, score_info.user.username, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_l_username)
    # 在线，离线
    w_line = DataText(195, 652, 30, '在线' if score_info.user.is_online else '离线', Torus_SemiBold,
                      anchor='lm')
    im = draw_text(im, w_line)
    # acc,cb,pp,300,100,50,miss
    if score_info.mode == 'osu':
        w_sspp = DataText(650, 550, 30, ss_pp, Torus_Regular, anchor='mm')
        im = draw_text(im, w_sspp)
        w_ifpp = DataText(770, 550, 30, if_pp, Torus_Regular, anchor='mm')
        im = draw_text(im, w_ifpp)
        w_pp = DataText(890, 550, 30, int(round(pp_info.pp, 0)), Torus_Regular, anchor='mm')
        w_aimpp = DataText(650, 645, 30, int(round(pp_info.pp_aim, 0)), Torus_Regular, anchor='mm')
        im = draw_text(im, w_aimpp)
        w_spdpp = DataText(770, 645, 30, int(round(pp_info.pp_speed, 0)), Torus_Regular, anchor='mm')
        im = draw_text(im, w_spdpp)
        w_accpp = DataText(890, 645, 30, int(round(pp_info.pp_acc, 0)), Torus_Regular, anchor='mm')
        im = draw_text(im, w_accpp)
        w_acc = DataText(1087, 550, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1315, 550, 30, f'{score_info.max_combo:,}/{mapinfo.max_combo:,}', Torus_Regular, anchor='mm')
        w_300 = DataText(1030, 645, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_100 = DataText(1144, 645, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_50 = DataText(1258, 645, 30, score_info.statistics.count_50, Torus_Regular, anchor='mm')
        im = draw_text(im, w_50)
        w_miss = DataText(1372, 645, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    elif score_info.mode == 'taiko':
        w_acc = DataText(1050, 550, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1202, 550, 30, f'{score_info.max_combo:,}/{mapinfo.max_combo:,}',
                           Torus_Regular, anchor='mm')
        w_pp = DataText(1352, 550, 30, f'{int(round(pp_info.pp, 0))}/{ss_pp}', Torus_Regular, anchor='mm')
        w_300 = DataText(1050, 645, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_100 = DataText(1202, 645, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_miss = DataText(1352, 645, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    elif score_info.mode == 'fruits':
        w_acc = DataText(1016, 550, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1180, 550, 30, f'{score_info.max_combo:,}/{mapinfo.max_combo:,}',
                           Torus_Regular, anchor='mm')
        w_pp = DataText(1344, 550, 30, f'{int(round(pp_info.pp, 0))}/{ss_pp}', Torus_Regular, anchor='mm')
        w_300 = DataText(995, 645, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_100 = DataText(1118, 645, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_katu = DataText(1242, 645, 30, score_info.statistics.count_katu, Torus_Regular, anchor='mm')
        im = draw_text(im, w_katu)
        w_miss = DataText(1365, 645, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    else:
        w_acc = DataText(935, 550, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1130, 550, 30, f'{score_info.max_combo:,}', Torus_Regular, anchor='mm')
        w_pp = DataText(1328, 550, 30, f'{int(round(pp_info.pp, 0))}/{ss_pp}', Torus_Regular, anchor='mm')
        w_geki = DataText(886, 645, 30, score_info.statistics.count_geki, Torus_Regular, anchor='mm')
        im = draw_text(im, w_geki)
        w_300 = DataText(984, 645, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_katu = DataText(1083, 645, 30, score_info.statistics.count_katu, Torus_Regular, anchor='mm')
        im = draw_text(im, w_katu)
        w_100 = DataText(1182, 645, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_50 = DataText(1280, 645, 30, score_info.statistics.count_50, Torus_Regular, anchor='mm')
        im = draw_text(im, w_50)
        w_miss = DataText(1378, 645, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    im = draw_text(im, w_acc)
    im = draw_text(im, w_maxcb)
    im = draw_text(im, w_pp)
    im = draw_text(im, w_300)
    im = draw_text(im, w_100)
    im = draw_text(im, w_miss)

    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg
