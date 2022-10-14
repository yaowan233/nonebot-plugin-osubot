import math
from datetime import datetime, timedelta
from io import BytesIO
from time import mktime, strptime
from typing import Optional, List, Union
from numbers import Real
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from nonebot.adapters.onebot.v11 import MessageSegment

from .api import osu_api, sayo_api, pp_api
from .schema import User, Score, Beatmap, SayoBeatmap, PP
from .mods import get_mods_list, calc_mods
from .file import re_map, get_projectimg, map_downloaded, osu_file_dl
from .database.models import UserData, InfoData
from .utils import update_user_info, GM, GMN, FGM

osufile = Path(__file__).parent / 'osufile'

Torus_Regular = osufile / 'fonts' / 'Torus Regular.otf'
Torus_SemiBold = osufile / 'fonts' / 'Torus SemiBold.otf'
Meiryo_Regular = osufile / 'fonts' / 'Meiryo Regular.ttf'
Meiryo_SemiBold = osufile / 'fonts' / 'Meiryo SemiBold.ttf'
Venera = osufile / 'fonts' / 'Venera.otf'


def image2bytesio(pic: Image):
    byt = BytesIO()
    pic.save(byt, "png")
    return byt


class DataText:
    # L=X轴，T=Y轴，size=字体大小，fontpath=字体文件，
    def __init__(self, length, height, size, text, path: Path, anchor='lt'):
        self.length = length
        self.height = height
        self.text = str(text)
        self.path = path
        self.font = ImageFont.truetype(str(self.path), size)
        self.anchor = anchor


def write_text(image, font, text='text', pos=(0, 0), color=(255, 255, 255, 255), anchor='lt'):
    rgba_image = image.convert('RGBA')
    text_overlay = Image.new('RGBA', rgba_image.size, (255, 255, 255, 0))
    image_draw = ImageDraw.Draw(text_overlay)
    image_draw.text(pos, text, font=font, fill=color, anchor=anchor)
    return Image.alpha_composite(rgba_image, text_overlay)


def draw_text(image, class_text: DataText, color=(255, 255, 255, 255)):
    font = class_text.font
    text = class_text.text
    anchor = class_text.anchor
    return write_text(image, font, text, (class_text.length, class_text.height), color, anchor)


def draw_fillet(img, radii):
    # 画圆（用于分离4个角）
    circle = Image.new('L', (radii * 2, radii * 2), 0)  # 创建一个黑色背景的画布
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radii * 2, radii * 2), fill=255)  # 画白色圆形
    # 原图
    img = img.convert("RGBA")
    w, h = img.size
    # 画4个角（将整圆分离为4个部分）
    alpha = Image.new('L', img.size, 255)
    alpha.paste(circle.crop((0, 0, radii, radii)), (0, 0))  # 左上角
    alpha.paste(circle.crop((radii, 0, radii * 2, radii)), (w - radii, 0))  # 右上角
    alpha.paste(circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii))  # 右下角
    alpha.paste(circle.crop((0, radii, radii, radii * 2)), (0, h - radii))  # 左下角
    # 白色区域透明可见，黑色区域不可见
    img.putalpha(alpha)
    return img


def info_calc(n1: Optional[Real], n2: Optional[Real], rank: bool = False, pp: bool = False):
    if not n1 or n2:
        return '', 0
    num = n1 - n2
    if num < 0:
        if rank:
            op, value = '↑', num * -1
        elif pp:
            op, value = '↓', num * -1
        else:
            op, value = '-', num * -1
    elif num > 0:
        if rank:
            op, value = '↓', num
        elif pp:
            op, value = '↑', num
        else:
            op, value = '+', num
    else:
        op, value = '', 0
    return [op, value]


def wedge_acc(acc: float) -> BytesIO:
    size = [acc, 100 - acc]
    insize = [60, 20, 7, 7, 5, 1]
    insizecolor = ['#ff5858', '#ea7948', '#d99d03', '#72c904', '#0096a2', '#be0089']
    fig, ax = plt.subplots()
    patches, texts = ax.pie(size, radius=1.1, startangle=90, counterclock=False, pctdistance=0.9,
                            wedgeprops=dict(width=0.27))
    ax.pie(insize, radius=0.8, colors=insizecolor, startangle=90, counterclock=False, pctdistance=0.9,
           wedgeprops=dict(width=0.05))
    patches[1].set_alpha(0)
    img = BytesIO()
    plt.savefig(img, transparent=True)
    return img


def crop_bg(size: str, path: Union[str, BytesIO, Path]):
    bg = Image.open(path).convert('RGBA')
    bg_w, bg_h = bg.size[0], bg.size[1]
    if size == 'BG':
        fix_w = 1500
        fix_h = 360
    elif size == 'H':
        fix_w = 540
        fix_h = 180
    elif size == 'HI':
        fix_w = 1000
        fix_h = 400
    elif size == 'MP':
        fix_w = 1200
        fix_h = 300
    elif size == 'MB':
        fix_w = 1200
        fix_h = 600
    else:
        raise
    # 固定比例
    fix_scale = fix_h / fix_w
    # 图片比例
    bg_scale = bg_h / bg_w
    # 当图片比例大于固定比例
    if bg_scale > fix_scale:
        # 长比例
        scale_width = fix_w / bg_w
        # 等比例缩放
        width = int(scale_width * bg_w)
        height = int(scale_width * bg_h)
        sf = bg.resize((width, height))
        # 计算上下裁切
        crop_height = (height - fix_h) / 2
        x1, y1, x2, y2 = 0, crop_height, width, height - crop_height
        # 裁切保存
        crop_img = sf.crop((x1, y1, x2, y2))
        return crop_img
    # 当图片比例小于固定比例
    elif bg_scale < fix_scale:
        # 宽比例
        scale_height = fix_h / bg_h
        # 等比例缩放
        width = int(scale_height * bg_w)
        height = int(scale_height * bg_h)
        sf = bg.resize((width, height))
        # 计算左右裁切
        crop_width = (width - fix_w) / 2
        x1, y1, x2, y2 = crop_width, 0, width - crop_width, height
        # 裁切保存
        crop_img = sf.crop((x1, y1, x2, y2))
        return crop_img
    else:
        sf = bg.resize((fix_w, fix_h))
        return sf


def stars_diff(mode: Union[str, int], stars: float):
    if mode == 0:
        mode = 'std'
    elif mode == 1:
        mode = 'taiko'
    elif mode == 2:
        mode = 'ctb'
    elif mode == 3:
        mode = 'mania'
    else:
        mode = 'stars'
    default = 115
    if stars < 1:
        xp = 0
        default = 120
    elif stars < 2:
        xp = 120
        default = 120
    elif stars < 3:
        xp = 240
    elif stars < 4:
        xp = 355
    elif stars < 5:
        xp = 470
    elif stars < 6:
        xp = 585
    elif stars < 7:
        xp = 700
    elif stars < 8:
        xp = 815
    else:
        return Image.open(osufile / 'work' / f'{mode}_expertplus.png').convert('RGBA')
    # 取色
    x = (stars - math.floor(stars)) * default + xp
    color = Image.open(osufile / 'work' / 'color.png').load()
    r, g, b = color[x, 1]
    # 打开底图
    im = Image.open(osufile / 'work' / f'{mode}.png').convert('RGBA')
    xx, yy = im.size
    # 填充背景
    sm = Image.new('RGBA', im.size, (r, g, b))
    sm.paste(im, (0, 0, xx, yy), im)
    # 把白色变透明
    for i in range(xx):
        for z in range(yy):
            data = sm.getpixel((i, z))
            if data.count(255) == 4:
                sm.putpixel((i, z), (255, 255, 255, 0))
    return sm


def get_modeimage(mode: int) -> Path:
    if mode == 0:
        img = 'pfm_std.png'
    elif mode == 1:
        img = 'pfm_taiko.png'
    elif mode == 2:
        img = 'pfm_ctb.png'
    else:
        img = 'pfm_mania.png'
    return osufile / img


def calc_songlen(length: int) -> str:
    map_len = list(divmod(int(length), 60))
    map_len[1] = map_len[1] if map_len[1] >= 10 else f'0{map_len[1]}'
    music_len = f'{map_len[0]}:{map_len[1]}'
    return music_len


async def draw_info(uid: Union[int, str], mode: str) -> Union[str, MessageSegment]:
    info_json = await osu_api('info', uid, mode)
    if isinstance(info_json, str):
        return info_json
    info = User(**info_json)
    statistics = info.statistics
    if statistics.play_count == 0:
        return f'此玩家尚未游玩过{GMN[mode]}模式'
    # 对比
    print()
    user = await InfoData.get_or_none(osu_id=info.id, osu_mode=FGM[mode])
    if user:
        n_crank, n_grank, n_pp, n_acc, n_pc, n_count = user.c_rank, user.g_rank, user.pp, user.acc, user.pc, user.count
    else:
        n_crank, n_grank, n_pp, n_acc, n_pc, n_count = statistics.country_rank, statistics.global_rank, \
                                                       statistics.pp, statistics.hit_accuracy, \
                                                       statistics.play_count, statistics.total_hits
    # 新建
    im = Image.new('RGBA', (1000, 1322))
    # 获取头图，头像，地区，状态，supporter
    user_header = await get_projectimg(info.cover_url)
    user_icon = await get_projectimg(info.avatar_url)
    country = osufile / 'flags' / f'{info.country_code}.png'
    supporter = osufile / 'work' / 'suppoter.png'
    exp_l = osufile / 'work' / 'left.png'
    exp_c = osufile / 'work' / 'center.png'
    exp_r = osufile / 'work' / 'right.png'
    # 头图
    header_img = crop_bg('HI', user_header)
    im.alpha_composite(header_img, (0, 100))
    # 底图
    info_bg = osufile / 'info.png'
    info_img = Image.open(info_bg).convert('RGBA')
    im.alpha_composite(info_img)
    # 头像
    icon_bg = Image.open(user_icon).convert('RGBA').resize((300, 300))
    icon_img = draw_fillet(icon_bg, 25)
    im.alpha_composite(icon_img, (50, 148))
    # 奖牌
    if statistics.badges:
        badges_num = len(statistics.badges)
        for num, badge in enumerate(statistics.badges):
            if badges_num <= 9:
                length = 50 + 100 * num
                height = 530
            elif num < 9:
                length = 50 + 100 * num
                height = 506
            else:
                length = 50 + 100 * (num - 9)
                height = 554
            badges_path = await get_projectimg(badge.image_url)
            badges_img = Image.open(badges_path).convert('RGBA').resize((86, 40))
            im.alpha_composite(badges_img, (length, height))
    else:
        w_badges = DataText(500, 545, 35, "You don't have a badge", Torus_Regular, anchor='mm')
        im = draw_text(im, w_badges)
    # 地区
    country_bg = Image.open(country).convert('RGBA').resize((80, 54))
    im.alpha_composite(country_bg, (400, 394))
    # supporter
    if info.has_supported:
        supporter_bg = Image.open(supporter).convert('RGBA').resize((54, 54))
        im.alpha_composite(supporter_bg, (400, 280))
    # 经验
    if statistics.level.progress != 0:
        exp_left_bg = Image.open(exp_l).convert('RGBA')
        im.alpha_composite(exp_left_bg, (50, 646))
        exp_width = statistics.level.progress * 7 - 3
        exp_center_bg = Image.open(exp_c).convert('RGBA').resize((exp_width, 10))
        im.alpha_composite(exp_center_bg, (54, 646))
        exp_right_bg = Image.open(exp_r).convert('RGBA')
        im.alpha_composite(exp_right_bg, (int(54 + exp_width), 646))
    # 模式
    w_mode = DataText(935, 50, 45, GMN[mode], Torus_Regular, anchor='rm')
    im = draw_text(im, w_mode)
    # 玩家名
    w_name = DataText(400, 205, 50, info.username, Torus_Regular, anchor='lm')
    im = draw_text(im, w_name)
    # 地区排名
    op, value = info_calc(statistics.country_rank, n_crank, rank=True)
    if not statistics.country_rank:
        t_crank = "#0"
    else:
        t_crank = f"#{statistics.country_rank:,}({op}{value:,})" \
            if value != 0 else f"#{statistics.country_rank:,}"
    w_crank = DataText(495, 448, 30, t_crank, Meiryo_Regular, anchor='lb')
    im = draw_text(im, w_crank)
    # 等级
    w_current = DataText(900, 650, 25, statistics.level.current, Torus_Regular, anchor='mm')
    im = draw_text(im, w_current)
    # 经验百分比
    w_progress = DataText(750, 660, 20, f'{statistics.level.progress}%', Torus_Regular, anchor='rt')
    im = draw_text(im, w_progress)
    # 全球排名
    if not statistics.global_rank:
        w_grank = DataText(55, 785, 35, "#0", Torus_Regular)
    else:
        w_grank = DataText(55, 785, 35, f"#{statistics.global_rank:,}", Torus_Regular)
    im = draw_text(im, w_grank)
    op, value = info_calc(statistics.global_rank, n_grank, rank=True)
    if value != 0:
        w_n_grank = DataText(65, 820, 20, f'{op}{value:,}', Meiryo_Regular)
        im = draw_text(im, w_n_grank)
    # pp
    w_pp = DataText(295, 785, 35, f'{statistics.pp:,}', Torus_Regular)
    im = draw_text(im, w_pp)
    op, value = info_calc(statistics.pp, n_pp, pp=True)
    if value != 0:
        w_n_pc = DataText(305, 820, 20, f'{op}{value:.2f}', Meiryo_Regular)
        im = draw_text(im, w_n_pc)
    # SS - A
    # gc_x = 493
    for gc_num, (_, num) in enumerate(statistics.grade_counts):
        w_ss_a = DataText(493 + 100 * gc_num, 775, 30, num, Torus_Regular, anchor='mt')
        im = draw_text(im, w_ss_a)
        # gc_x+=100
    # rank分
    w_r_score = DataText(935, 895, 40, f'{statistics.ranked_score:,}', Torus_Regular, anchor='rt')
    im = draw_text(im, w_r_score)
    # acc
    op, value = info_calc(statistics.hit_accuracy, n_acc)
    t_acc = f'{statistics.hit_accuracy:.2f}%({op}{value:.2f}%)' if value != 0 else f'{statistics.hit_accuracy:.2f}%'
    w_acc = DataText(935, 965, 40, t_acc, Torus_Regular, anchor='rt')
    im = draw_text(im, w_acc)
    # 游玩次数
    op, value = info_calc(statistics.play_count, n_pc)
    t_pc = f'{statistics.play_count:,}({op}{value:,})' if value != 0 else f'{statistics.play_count:,}'
    w_pc = DataText(935, 1035, 40, t_pc, Torus_Regular, anchor='rt')
    im = draw_text(im, w_pc)
    # 总分
    w_t_score = DataText(935, 1105, 40, f'{statistics.total_score:,}', Torus_Regular, anchor='rt')
    im = draw_text(im, w_t_score)
    # 总命中
    op, value = info_calc(statistics.total_hits, n_count)
    t_count = f'{statistics.total_hits:,}({op}{value:,})' if value != 0 else f'{statistics.total_hits:,}'
    w_conut = DataText(935, 1175, 40, t_count, Torus_Regular, anchor='rt')
    im = draw_text(im, w_conut)
    # 游玩时间
    sec = timedelta(seconds=statistics.play_time)
    d_time = datetime(1, 1, 1) + sec
    t_time = "%dd %dh %dm %ds" % (sec.days, d_time.hour, d_time.minute, d_time.second)
    w_name = DataText(935, 1245, 40, t_time, Torus_Regular, anchor='rt')
    im = draw_text(im, w_name)
    # 输出
    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg


async def draw_score(project: str,
                     uid: int,
                     mode: str,
                     mods: Optional[List[str]],
                     best: int = 0,
                     mapid: int = 0) -> Union[str, MessageSegment]:
    score_json = await osu_api(project, uid, mode, mapid)
    if not score_json:
        return '未查询到游玩记录'
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
        if not calc_mods(score_info.mods) == calc_mods(mods):
            return '非常抱歉，暂不支持指定mods查分>_<'
    else:
        raise 'Project Error'
    map_json = await osu_api('map', map_id=score_info.beatmap.id)
    mapinfo = Beatmap(**map_json)
    header = await osu_api('info', uid)
    headericon = header['cover_url']

    # 下载地图
    dirpath = await map_downloaded(str(score_info.beatmap.beatmapset_id))
    osu = await osu_file_dl(score_info.beatmap.id)
    # pp
    pp_data = await pp_api(FGM[score_info.mode], score_info)
    pp_info = PP(**pp_data)
    # 新建图片
    im = Image.new('RGBA', (1500, 800))
    # 获取cover并裁剪，高斯，降低亮度
    cover = re_map(osu)
    if cover == 'mapbg.png':
        cover_path = osufile / 'work' / cover
    else:
        cover_path = dirpath / cover
    cover_crop = crop_bg('BG', cover_path)
    cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(1))
    cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
    im.alpha_composite(cover_img, (0, 200))
    # 获取成绩背景做底图
    bg = get_modeimage(FGM[score_info.mode])
    recent_bg = Image.open(bg).convert('RGBA')
    im.alpha_composite(recent_bg)
    # 模式
    mode_bg = stars_diff(score_info.mode, pp_info.StarRating)
    mode_img = mode_bg.resize((30, 30))
    im.alpha_composite(mode_img, (75, 154))
    # 难度星星
    stars_bg = stars_diff('stars', pp_info.StarRating)
    stars_img = stars_bg.resize((23, 23))
    im.alpha_composite(stars_img, (134, 158))
    # mods
    if 'HD' in score_info.mods or 'FL' in score_info.mods:
        ranking = ['XH', 'SH', 'A', 'B', 'C', 'D', 'F']
    else:
        ranking = ['X', 'S', 'A', 'B', 'C', 'D', 'F']
    if score_info.mods:
        for mods_num, s_mods in enumerate(score_info.mods):
            mods_bg = osufile / 'mods' / f'{s_mods}.png'
            mods_img = Image.open(mods_bg).convert('RGBA')
            im.alpha_composite(mods_img, (500 + 50 * mods_num, 240))
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
        im.alpha_composite(rank_bg, (75, 243 + 39 * rank_num))
    # 成绩+acc
    score_acc = wedge_acc(score_info.accuracy * 100)
    score_acc_bg = Image.open(score_acc).convert('RGBA').resize((576, 432))
    im.alpha_composite(score_acc_bg, (15, 153))
    # 获取头图，头像，地区，状态，support
    user_headericon = await get_projectimg(headericon)
    user_icon = await get_projectimg(score_info.user.avatar_url)
    # 头图
    headericon_crop = crop_bg('H', user_headericon)
    headericon_gb = headericon_crop.filter(ImageFilter.GaussianBlur(1))
    headericon_img = ImageEnhance.Brightness(headericon_gb).enhance(2 / 4.0)
    headericon_d = draw_fillet(headericon_img, 15)
    im.alpha_composite(headericon_d, (50, 591))
    # 头像
    icon_bg = Image.open(user_icon).convert('RGBA').resize((90, 90))
    icon_img = draw_fillet(icon_bg, 15)
    im.alpha_composite(icon_img, (90, 606))
    # 地区
    country = osufile / 'flags' / f'{score_info.user.country_code}.png'
    country_bg = Image.open(country).convert('RGBA').resize((58, 39))
    im.alpha_composite(country_bg, (195, 606))
    # 在线状态
    status = osufile / 'work' / ('on-line.png' if score_info.user.is_online else 'off-line.png')
    status_bg = Image.open(status).convert('RGBA').resize((45, 45))
    im.alpha_composite(status_bg, (114, 712))
    # supporter
    if score_info.user.is_supporter:
        supporter = osufile / 'work' / 'suppoter.png'
        supporter_bg = Image.open(supporter).convert('RGBA').resize((40, 40))
        im.alpha_composite(supporter_bg, (267, 606))
    # cs, ar, od, hp, stardiff
    mapdiff = [mapinfo.cs, mapinfo.drain, mapinfo.accuracy, mapinfo.ar, mapinfo.difficulty_rating]
    for num, i in enumerate(mapdiff):
        color = (255, 255, 255, 255)
        if num == 4:
            color = (255, 204, 34, 255)
        diff_len = int(250 * i / 10) if i <= 10 else 250
        diff_len = Image.new('RGBA', (diff_len, 8), color)
        im.alpha_composite(diff_len, (1190, 386 + 35 * num))
        w_diff = DataText(1470, 386 + 35 * num, 20, i, Torus_SemiBold, anchor='mm')
        im = draw_text(im, w_diff)
    # 时长 - 滑条
    diff_info = calc_songlen(mapinfo.total_length), mapinfo.bpm, mapinfo.count_circles, mapinfo.count_sliders
    for num, i in enumerate(diff_info):
        w_info = DataText(1070 + 120 * num, 325, 20, i, Torus_Regular, anchor='lm')
        im = draw_text(im, w_info, (255, 204, 34, 255))
    # 状态
    w_status = DataText(1400, 264, 20, mapinfo.status.capitalize(), Torus_SemiBold, anchor='mm')
    im = draw_text(im, w_status)
    # mapid
    w_mapid = DataText(1425, 40, 27, f'Setid: {score_info.beatmap.beatmapset_id}  |  Mapid: {score_info.id}',
                       Torus_SemiBold, anchor='rm')
    im = draw_text(im, w_mapid)
    # 曲名
    w_title = DataText(75, 118, 30, f'{mapinfo.beatmapset.title} | by {mapinfo.beatmapset.artist_unicode}',
                       Meiryo_SemiBold, anchor='lm')
    im = draw_text(im, w_title)
    # 星级
    w_diff = DataText(162, 169, 18, f'{pp_info.StarRating:.1f}', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_diff)
    # 谱面版本，mapper
    w_version = DataText(225, 169, 22, f'{mapinfo.version} | mapper by {mapinfo.beatmapset.creator}', Torus_SemiBold,
                         anchor='lm')
    im = draw_text(im, w_version)
    # 评价
    w_rank = DataText(309, 375, 75, score_info.rank, Venera, anchor='mm')
    im = draw_text(im, w_rank)
    # 分数
    w_score = DataText(498, 331, 75, f'{score_info.score:,}', Torus_Regular, anchor='lm')
    im = draw_text(im, w_score)
    # 玩家
    w_played = DataText(498, 396, 18, 'Played by:', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_played)
    w_username = DataText(630, 396, 18, score_info.user.username, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_username)
    # 时间
    w_date = DataText(498, 421, 18, 'Submitted on:', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_date)
    old_time = datetime.strptime(score_info.created_at.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S')
    new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    w_time = DataText(630, 421, 18, new_time, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_time)
    # 全球排名
    w_grank = DataText(513, 496, 24, grank, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_grank)
    # 左下玩家名
    w_l_username = DataText(195, 670, 24, score_info.user.username, Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_l_username)
    # 在线，离线
    w_line = DataText(195, 732, 30, 'online' if score_info.user.is_online else 'offline', Torus_SemiBold,
                      anchor='lm')
    im = draw_text(im, w_line)
    # acc,cb,pp,300,100,50,miss
    if score_info.mode == 'osu':
        w_sspp = DataText(650, 625, 30, pp_info.sspp, Torus_Regular, anchor='mm')
        im = draw_text(im, w_sspp)
        w_ifpp = DataText(770, 625, 30, pp_info.ifpp, Torus_Regular, anchor='mm')
        im = draw_text(im, w_ifpp)
        w_pp = DataText(890, 625, 30, pp_info.pp, Torus_Regular, anchor='mm')
        w_aimpp = DataText(650, 720, 30, pp_info.aim, Torus_Regular, anchor='mm')
        im = draw_text(im, w_aimpp)
        w_spdpp = DataText(770, 720, 30, pp_info.speed, Torus_Regular, anchor='mm')
        im = draw_text(im, w_spdpp)
        w_accpp = DataText(890, 720, 30, pp_info.accuracy, Torus_Regular, anchor='mm')
        im = draw_text(im, w_accpp)
        w_acc = DataText(1087, 625, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1315, 625, 30, f'{score_info.max_combo:,}/{mapinfo.max_combo:,}', Torus_Regular, anchor='mm')
        w_300 = DataText(1030, 720, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_100 = DataText(1144, 720, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_50 = DataText(1258, 720, 30, score_info.statistics.count_50, Torus_Regular, anchor='mm')
        im = draw_text(im, w_50)
        w_miss = DataText(1372, 720, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    elif score_info.mode == 'taiko':
        w_acc = DataText(1050, 625, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1202, 625, 30, f'{score_info.max_combo:,}/{mapinfo.max_combo:,}',
                           Torus_Regular, anchor='mm')
        w_pp = DataText(1352, 625, 30, f'{pp_info.pp}/{pp_info.ifpp}', Torus_Regular, anchor='mm')
        w_300 = DataText(1050, 720, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_100 = DataText(1202, 720, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_miss = DataText(1352, 720, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    elif score_info.mode == 'fruits':
        w_acc = DataText(1016, 625, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1180, 625, 30, f'{score_info.max_combo:,}/{mapinfo.max_combo:,}',
                           Torus_Regular, anchor='mm')
        w_pp = DataText(1344, 625, 30, f'{pp_info.pp}/{pp_info.ifpp}', Torus_Regular, anchor='mm')
        w_300 = DataText(995, 720, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_100 = DataText(1118, 720, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_katu = DataText(1242, 720, 30, score_info.statistics.count_katu, Torus_Regular, anchor='mm')
        im = draw_text(im, w_katu)
        w_miss = DataText(1365, 720, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    else:
        w_acc = DataText(935, 625, 30, f'{score_info.accuracy * 100:.2f}%', Torus_Regular, anchor='mm')
        w_maxcb = DataText(1130, 625, 30, f'{score_info.max_combo:,}', Torus_Regular, anchor='mm')
        w_pp = DataText(1328, 625, 30, f'{pp_info.pp}/{pp_info.ifpp}', Torus_Regular, anchor='mm')
        w_geki = DataText(886, 720, 30, score_info.statistics.count_geki, Torus_Regular, anchor='mm')
        im = draw_text(im, w_geki)
        w_300 = DataText(984, 720, 30, score_info.statistics.count_300, Torus_Regular, anchor='mm')
        w_katu = DataText(1083, 720, 30, score_info.statistics.count_katu, Torus_Regular, anchor='mm')
        im = draw_text(im, w_katu)
        w_100 = DataText(1182, 720, 30, score_info.statistics.count_100, Torus_Regular, anchor='mm')
        w_50 = DataText(1280, 720, 30, score_info.statistics.count_50, Torus_Regular, anchor='mm')
        im = draw_text(im, w_50)
        w_miss = DataText(1378, 720, 30, score_info.statistics.count_miss, Torus_Regular, anchor='mm')
    im = draw_text(im, w_acc)
    im = draw_text(im, w_maxcb)
    im = draw_text(im, w_pp)
    im = draw_text(im, w_300)
    im = draw_text(im, w_100)
    im = draw_text(im, w_miss)

    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg


def image_pfm(project: str, user: str, score_ls: List[Score], mode: str, low_bound: int = 0, high_bound: int = 0) -> \
        Union[str, MessageSegment]:
    bplist_len = len(score_ls)
    im = Image.new('RGBA', (1500, 180 + 82 * (bplist_len - 1)), (31, 41, 46, 255))
    bp_bg = osufile / 'Best Performance.png'
    bg_img = Image.open(bp_bg).convert('RGBA')
    im.alpha_composite(bg_img)
    f_div = Image.new('RGBA', (1500, 2), (255, 255, 255, 255)).convert('RGBA')
    im.alpha_composite(f_div, (0, 100))
    if project == 'bp':
        uinfo = f"{user}'s | {mode.capitalize()} | BP {low_bound} - {high_bound}"
    else:
        uinfo = f"{user}'s | {mode.capitalize()} | Today New BP"
    w_user = DataText(1450, 50, 25, uinfo, Torus_SemiBold, anchor='rm')
    im = draw_text(im, w_user)
    for num, bp in enumerate(score_ls):
        h_num = 82 * num
        # mods
        if bp.mods:
            for mods_num, s_mods in enumerate(bp.mods):
                mods_bg = osufile / 'mods' / f'{s_mods}.png'
                mods_img = Image.open(mods_bg).convert('RGBA')
                im.alpha_composite(mods_img, (1000 + 50 * mods_num, 126 + h_num))
            if (bp.rank == 'X' or bp.rank == 'S') and ('HD' in bp.mods or 'FL' in bp.mods):
                bp.rank += 'H'
        # BP排名
        rank_bp = DataText(15, 144 + h_num, 20, num + 1, Meiryo_Regular, anchor='lm')
        im = draw_text(im, rank_bp)
        # rank
        rank_img = osufile / 'ranking' / f'ranking-{bp.rank}.png'
        rank_bg = Image.open(rank_img).convert('RGBA').resize((64, 32))
        im.alpha_composite(rank_bg, (45, 128 + h_num))
        # 曲名&作曲
        w_title_artist = DataText(125, 130 + h_num, 20, f'{bp.beatmapset.title}'
                                                        f' | by {bp.beatmapset.artist}', Meiryo_Regular,
                                  anchor='lm')
        im = draw_text(im, w_title_artist)
        # 地图版本&时间
        old_time = datetime.strptime(bp.created_at.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S')
        new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        w_version_time = DataText(125, 158 + h_num, 18, f'{bp.beatmap.version} | {new_time}', Torus_Regular,
                                  anchor='lm')
        im = draw_text(im, w_version_time, color=(238, 171, 0, 255))
        # acc
        w_acc = DataText(1250, 130 + h_num, 22, f'{bp.accuracy * 100:.2f}%', Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_acc, color=(238, 171, 0, 255))
        # mapid
        w_mapid = DataText(1250, 158 + h_num, 18, f'ID: {bp.beatmap.id}', Torus_Regular, anchor='lm')
        im = draw_text(im, w_mapid)
        # pp
        w_pp = DataText(1420, 140 + h_num, 25, int(bp.pp), Torus_SemiBold, anchor='rm')
        im = draw_text(im, w_pp, (255, 102, 171, 255))
        w_n_pp = DataText(1450, 140 + h_num, 25, 'pp', Torus_SemiBold, anchor='rm')
        im = draw_text(im, w_n_pp, (209, 148, 176, 255))
        # 分割线
        div = Image.new('RGBA', (1450, 2), (46, 53, 56, 255)).convert('RGBA')
        im.alpha_composite(div, (25, 180 + h_num))

    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg


async def best_pfm(project: str, uid: int, mode: str, mods: Optional[List],
                   low_bound: int = 0, high_bound: int = 0) -> Union[str, MessageSegment]:
    bp_info = await osu_api('bp', uid, mode)
    if isinstance(bp_info, str):
        return bp_info
    score_ls = [Score(**i) for i in bp_info]
    user = bp_info[0]['user']['username']
    if project == 'bp':
        if mods:
            mods_ls = get_mods_list(score_ls, mods)
            if low_bound > len(mods_ls):
                return f'未找到开启 {"|".join(mods)} Mods的成绩'
            if high_bound > len(mods_ls):
                mods_ls = mods_ls[low_bound - 1:]
            else:
                mods_ls = mods_ls[low_bound - 1: high_bound]
            score_ls = [score_ls[i] for i in mods_ls]
        else:
            score_ls = score_ls[low_bound - 1: high_bound]
    elif project == 'tbp':
        ls = []
        for i, score in enumerate(score_ls):
            today = datetime.now().date()
            today_stamp = mktime(strptime(str(today), '%Y-%m-%d'))
            playtime = datetime.strptime(score.created_at.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S') + timedelta(
                hours=8)
            play_stamp = mktime(strptime(str(playtime), '%Y-%m-%d %H:%M:%S'))

            if play_stamp > today_stamp:
                ls.append(i)
        score_ls = [score_ls[i] for i in ls]
        if not score_ls:
            return '今天没有新增的BP成绩'
    msg = image_pfm(project, user, score_ls, mode, low_bound, high_bound)
    return msg


async def map_info(mapid: int, mods: list) -> Union[str, MessageSegment]:
    info = await osu_api('map', map_id=mapid)
    if not info:
        return '未查询到该地图信息'
    if isinstance(info, str):
        return info
    mapinfo = Beatmap(**info)
    diffinfo = calc_songlen(mapinfo.total_length), mapinfo.bpm, mapinfo.count_circles, mapinfo.count_sliders
    # 获取地图
    dirpath = await map_downloaded(str(mapinfo.beatmapset_id))
    osu = await osu_file_dl(mapid)
    # pp
    data = {
        'BeatmapID': mapid,
        'Mode': FGM[mapinfo.mode],
        'Mods': mods
    }
    pp = await pp_api(FGM[mapinfo.mode], None, data=data)
    pp_info = PP(**pp)
    # 计算时间
    if mapinfo.beatmapset.ranked_date:
        old_time = datetime.strptime(mapinfo.beatmapset.ranked_date.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S')
        new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    else:
        new_time = '??-??-?? ??:??:??'
    # BG做地图
    im = Image.new('RGBA', (1200, 600))
    cover = re_map(osu)
    cover_crop = crop_bg('MB', dirpath / cover)
    cover_img = ImageEnhance.Brightness(cover_crop).enhance(2 / 4.0)
    im.alpha_composite(cover_img)
    # 获取地图info
    map_bg = osufile / 'beatmapinfo.png'
    mapbg = Image.open(map_bg).convert('RGBA')
    im.alpha_composite(mapbg)
    # 模式
    mode_bg = stars_diff(mapinfo.mode, pp_info.StarRating)
    mode_img = mode_bg.resize((50, 50))
    im.alpha_composite(mode_img, (50, 100))
    # cs - diff
    mapdiff = [mapinfo.cs, mapinfo.drain, mapinfo.accuracy, mapinfo.ar, pp_info.StarRating]
    for num, i in enumerate(mapdiff):
        color = (255, 255, 255, 255)
        if num == 4:
            color = (255, 204, 34, 255)
        difflen = int(250 * i / 10) if i <= 10 else 250
        diff_len = Image.new('RGBA', (difflen, 8), color)
        im.alpha_composite(diff_len, (890, 426 + 35 * num))
        w_diff = DataText(1170, 426 + 35 * num, 20, i, Torus_SemiBold, anchor='mm')
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
    w_title = DataText(50, 170, 30, mapinfo.beatmapset.title, Meiryo_SemiBold)
    im = draw_text(im, w_title)
    # 曲师
    w_artist = DataText(50, 210, 25, f'by {mapinfo.beatmapset.artist_unicode}', Meiryo_SemiBold)
    im = draw_text(im, w_artist)
    # 来源
    w_source = DataText(50, 260, 25, f'Source:{mapinfo.beatmapset.source}', Meiryo_SemiBold)
    im = draw_text(im, w_source)
    # mapper
    w_mapper_by = DataText(160, 400, 20, 'mapper by:', Torus_SemiBold)
    im = draw_text(im, w_mapper_by)
    w_mapper = DataText(160, 425, 20, mapinfo.beatmapset.creator, Torus_SemiBold)
    im = draw_text(im, w_mapper)
    # ranked时间
    w_time_by = DataText(160, 460, 20, 'ranked by:', Torus_SemiBold)
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
    w_mapcb = DataText(50, 570, 20, f'Max Combo: {mapinfo.max_combo}', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_mapcb)
    # pp
    w_pp = DataText(320, 570, 20, f'SS PP: {pp}', Torus_SemiBold, anchor='lm')
    im = draw_text(im, w_pp)
    # 输出
    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg


async def bmap_info(mapid, op: bool = False) -> Union[str, MessageSegment]:
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
        return '未查询到地图'
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
    w_title = DataText(25, 40, 38, data.titleU, Meiryo_SemiBold)
    im = draw_text(im, w_title)
    # 曲师
    w_artist = DataText(25, 75, 20, f'by {data.artistU}', Meiryo_SemiBold)
    im = draw_text(im, w_artist)
    # mapper
    w_mapper = DataText(25, 110, 20, f'mapper by {data.creator}', Torus_SemiBold)
    im = draw_text(im, w_mapper)
    # rank时间
    if data.approved_date == -1:
        approved_date = '??-??-?? ??:??:??'
    else:
        datearray = datetime.utcfromtimestamp(data.approved_date)
        approved_date = (datearray + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    w_apptime = DataText(25, 145, 20, f'Approved Time: {approved_date}', Torus_SemiBold)
    im = draw_text(im, w_apptime)
    # 来源
    w_source = DataText(25, 180, 20, f'Source: {data.source}', Meiryo_SemiBold)
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
            bar_bg = osufile / 'work' / 'bmap.png'
            bar_img = Image.open(bar_bg).convert('RGBA')
            im.alpha_composite(bar_img, (10, 365 + h_num))
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
            w_star = DataText(80, 328 + h_num, 20, cmap.star, Torus_SemiBold, anchor='lm')
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


async def bindinfo(project: str, uid, qid) -> str:
    info = await osu_api(project, uid, GM[0])
    if not info:
        return '未查询到该玩家'
    elif isinstance(info, str):
        return info
    uid = info['id']
    name = info['username']
    await UserData.create(user_id=qid, osu_id=uid, osu_name=name, osu_mode=0)
    await update_user_info(uid)
    msg = f'用户 {name} 已成功绑定QQ {qid}'
    return msg


async def get_map_bg(mapid: Union[str, int]) -> Union[str, MessageSegment]:
    info = await osu_api('map', map_id=mapid)
    if not info:
        return '未查询到该地图'
    elif isinstance(info, str):
        return info
    setid: int = info['beatmapset_id']
    dirpath = await map_downloaded(str(setid))
    osu = await osu_file_dl(mapid)
    path = re_map(osu)
    msg = MessageSegment.image(dirpath / path)
    return msg
