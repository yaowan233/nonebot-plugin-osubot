import base64
import math
import traceback
from datetime import datetime, timedelta
from typing import Optional
from numbers import Real

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from nonebot.adapters.onebot.v11 import MessageSegment

from .api import osu_api, sayo_api
from .data import SayoInfo, UserInfo, ScoreInfo, Beatmapset
from .file import *
from .pp import *
from .sql import *

USER = UserSQL()
osufile = os.path.join(os.path.dirname(__file__), 'osufile')

Torus_Regular = os.path.join(osufile, 'fonts', 'Torus Regular.otf')
Torus_SemiBold = os.path.join(osufile, 'fonts', 'Torus SemiBold.otf')
Meiryo_Regular = os.path.join(osufile, 'fonts', 'Meiryo Regular.ttf')
Meiryo_SemiBold = os.path.join(osufile, 'fonts', 'Meiryo SemiBold.ttf')
Venera = os.path.join(osufile, 'fonts', 'Venera.otf')

GM = {0: 'osu', 1: 'taiko', 2: 'fruits', 3: 'mania'}
GMN = {'osu': 'Std', 'taiko': 'Taiko', 'fruits': 'Ctb', 'mania': 'Mania'}
FGM = {'osu': 0, 'taiko': 1, 'fruits': 2, 'mania': 3}


class Tobase:

    def __init__(self, img: str, format: Optional[str] = 'PNG'):
        """`img : Union[str, Image] 图片`
        `format : Optional[str] 图片类型，默认PNG`"""
        self.img = img
        self.format = format

    def __b64str__(self, bytes: BytesIO) -> str:
        if isinstance(bytes, BytesIO):
            bytes = bytes.getvalue()
        else:
            bytes = bytes
        base64_str = base64.b64encode(bytes).decode()
        return 'base64://' + base64_str

    def image(self) -> str:
        '''`Image` 图片转 `base64` 编码'''
        bytes = BytesIO()
        self.img.save(bytes, self.format)
        return self.__b64str__(bytes)


class datatext:
    # L=X轴，T=Y轴，size=字体大小，fontpath=字体文件，
    def __init__(self, L, T, size, text, path, anchor='lt'):
        self.L = L
        self.T = T
        self.text = str(text)
        self.path = path
        self.font = ImageFont.truetype(self.path, size)
        self.anchor = anchor


def write_text(image, font, text='text', pos=(0, 0), color=(255, 255, 255, 255), anchor='lt'):
    rgba_image = image.convert('RGBA')
    text_overlay = Image.new('RGBA', rgba_image.size, (255, 255, 255, 0))
    image_draw = ImageDraw.Draw(text_overlay)
    image_draw.text(pos, text, font=font, fill=color, anchor=anchor)
    return Image.alpha_composite(rgba_image, text_overlay)


def draw_text(image, class_text: datatext, color=(255, 255, 255, 255)):
    font = class_text.font
    text = class_text.text
    anchor = class_text.anchor
    return write_text(image, font, text, (class_text.L, class_text.T), color, anchor)


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


def info_calc(n1: Real, n2: Real, rank: bool = False, pp: bool = False):
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


def crop_bg(size: str, path: Union[str, BytesIO]):
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
        return Image.open(os.path.join(osufile, 'work', f'{mode}_expertplus.png')).convert('RGBA')
    # 取色
    x = (stars - math.floor(stars)) * default + xp
    color = Image.open(os.path.join(osufile, 'work', 'color.png')).load()
    r, g, b = color[x, 1]
    # 打开底图
    im = Image.open(os.path.join(osufile, 'work', f'{mode}.png')).convert('RGBA')
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


def get_modeimage(mode: int) -> str:
    if mode == 0:
        img = 'pfm_std.png'
    elif mode == 1:
        img = 'pfm_taiko.png'
    elif mode == 2:
        img = 'pfm_ctb.png'
    else:
        img = 'pfm_mania.png'
    return os.path.join(osufile, img)


def calc_songlen(len: int) -> str:
    map_len = list(divmod(int(len), 60))
    map_len[1] = map_len[1] if map_len[1] >= 10 else f'0{map_len[1]}'
    music_len = f'{map_len[0]}:{map_len[1]}'
    return music_len


def osubytes(osufile: bytes) -> TextIOWrapper:
    return TextIOWrapper(BytesIO(osufile), 'utf-8')


async def draw_info(uid: Union[int, str], mode: str, isint: bool) -> Union[str, MessageSegment]:
    try:
        info_json = await osu_api('info', uid, mode, isint=isint)
        if not info_json:
            return '未查询到该玩家'
        if isinstance(info_json, str):
            return info_json
        info = UserInfo(info_json)
        if info.play_count == 0:
            return f'此玩家尚未游玩过{GMN[mode]}模式'
        # 对比
        user = USER.get_info(info.uid, FGM[mode])
        if user:
            n_crank, n_grank, n_pp, n_acc, n_pc, n_count = user
        else:
            n_crank, n_grank, n_pp, n_acc, n_pc, n_count = info.crank, info.grank, info.pp, info.acc, info.play_count, info.count
        # 新建
        im = Image.new('RGBA', (1000, 1322))
        # 获取头图，头像，地区，状态，supporter
        user_header = await get_projectimg(info.cover_url)
        user_icon = await get_projectimg(info.icon)
        country = os.path.join(osufile, 'flags', f'{info.country_code}.png')
        supporter = os.path.join(osufile, 'work', 'suppoter.png')
        exp_l = os.path.join(osufile, 'work', 'left.png')
        exp_c = os.path.join(osufile, 'work', 'center.png')
        exp_r = os.path.join(osufile, 'work', 'right.png')
        # 头图
        header_img = crop_bg('HI', user_header)
        im.alpha_composite(header_img, (0, 100))
        # 底图
        info_bg = os.path.join(osufile, 'info.png')
        info_img = Image.open(info_bg).convert('RGBA')
        im.alpha_composite(info_img)
        # 头像
        icon_bg = Image.open(user_icon).convert('RGBA').resize((300, 300))
        icon_img = draw_fillet(icon_bg, 25)
        im.alpha_composite(icon_img, (50, 148))
        # 奖牌
        if info.badges:
            badges_num = len(info.badges)
            for num, _ in enumerate(info.badges):
                if badges_num <= 9:
                    L = 50 + 100 * num
                    T = 530
                elif num < 9:
                    L = 50 + 100 * num
                    T = 506
                else:
                    L = 50 + 100 * (num - 9)
                    T = 554
                badges_path = await get_projectimg(_['image_url'])
                badges_img = Image.open(badges_path).convert('RGBA').resize((86, 40))
                im.alpha_composite(badges_img, (L, T))
        else:
            w_badges = datatext(500, 545, 35, "You don't have a badge", Torus_Regular, anchor='mm')
            im = draw_text(im, w_badges)
        # 地区
        country_bg = Image.open(country).convert('RGBA').resize((80, 54))
        im.alpha_composite(country_bg, (400, 394))
        # supporter
        if info.supporter:
            supporter_bg = Image.open(supporter).convert('RGBA').resize((54, 54))
            im.alpha_composite(supporter_bg, (400, 280))
        # 经验
        if info.progress != 0:
            exp_left_bg = Image.open(exp_l).convert('RGBA')
            im.alpha_composite(exp_left_bg, (50, 646))
            exp_width = info.progress * 7 - 3
            exp_center_bg = Image.open(exp_c).convert('RGBA').resize((exp_width, 10))
            im.alpha_composite(exp_center_bg, (54, 646))
            exp_right_bg = Image.open(exp_r).convert('RGBA')
            im.alpha_composite(exp_right_bg, (int(54 + exp_width), 646))
        # 模式
        w_mode = datatext(935, 50, 45, GMN[mode], Torus_Regular, anchor='rm')
        im = draw_text(im, w_mode)
        # 玩家名
        w_name = datatext(400, 205, 50, info.username, Torus_Regular, anchor='lm')
        im = draw_text(im, w_name)
        # 地区排名
        op, value = info_calc(info.crank, n_crank, rank=True)
        t_crank = f'#{info.crank:,}({op}{value:,})' if value != 0 else f'#{info.crank:,}'
        w_crank = datatext(495, 448, 30, t_crank, Meiryo_Regular, anchor='lb')
        im = draw_text(im, w_crank)
        # 等级
        w_current = datatext(900, 650, 25, info.current, Torus_Regular, anchor='mm')
        im = draw_text(im, w_current)
        # 经验百分比
        w_progress = datatext(750, 660, 20, f'{info.progress}%', Torus_Regular, anchor='rt')
        im = draw_text(im, w_progress)
        # 全球排名
        w_grank = datatext(55, 785, 35, f'#{info.grank:,}', Torus_Regular)
        im = draw_text(im, w_grank)
        op, value = info_calc(info.grank, n_grank, rank=True)
        if value != 0:
            w_n_grank = datatext(65, 820, 20, f'{op}{value:,}', Meiryo_Regular)
            im = draw_text(im, w_n_grank)
        # pp
        w_pp = datatext(295, 785, 35, f'{info.pp:,}', Torus_Regular)
        im = draw_text(im, w_pp)
        op, value = info_calc(info.pp, n_pp, pp=True)
        if value != 0:
            w_n_pc = datatext(305, 820, 20, f'{op}{value:.2f}', Meiryo_Regular)
            im = draw_text(im, w_n_pc)
        # SS - A
        # gc_x = 493
        for gc_num, i in enumerate(info.gc):
            w_ss_a = datatext(493 + 100 * gc_num, 775, 30, f'{i:,}', Torus_Regular, anchor='mt')
            im = draw_text(im, w_ss_a)
            # gc_x+=100
        # rank分
        w_r_score = datatext(935, 895, 40, f'{info.r_score:,}', Torus_Regular, anchor='rt')
        im = draw_text(im, w_r_score)
        # acc
        op, value = info_calc(info.acc, n_acc)
        t_acc = f'{info.acc:.2f}%({op}{value:.2f}%)' if value != 0 else f'{info.acc:.2f}%'
        w_acc = datatext(935, 965, 40, t_acc, Torus_Regular, anchor='rt')
        im = draw_text(im, w_acc)
        # 游玩次数
        op, value = info_calc(info.play_count, n_pc)
        t_pc = f'{info.play_count:,}({op}{value:,})' if value != 0 else f'{info.play_count:,}'
        w_pc = datatext(935, 1035, 40, t_pc, Torus_Regular, anchor='rt')
        im = draw_text(im, w_pc)
        # 总分
        w_t_score = datatext(935, 1105, 40, f'{info.t_score:,}', Torus_Regular, anchor='rt')
        im = draw_text(im, w_t_score)
        # 总命中
        op, value = info_calc(info.count, n_count)
        t_count = f'{info.count:,}({op}{value:,})' if value != 0 else f'{info.count:,}'
        w_conut = datatext(935, 1175, 40, t_count, Torus_Regular, anchor='rt')
        im = draw_text(im, w_conut)
        # 游玩时间
        sec = timedelta(seconds=info.play_time)
        d_time = datetime(1, 1, 1) + sec
        t_time = "%dd %dh %dm %ds" % (sec.days, d_time.hour, d_time.minute, d_time.second)
        w_name = datatext(935, 1245, 40, t_time, Torus_Regular, anchor='rt')
        im = draw_text(im, w_name)
        # 输出
        base = Tobase(im).image()
        msg = MessageSegment.image(base)
    except Exception as e:
        logger.error(f'制图错误：{traceback.print_exc()}')
        msg = f'Error: {type(e)}'
    return msg


async def draw_score(project: str,
                     uid: str,
                     mode: str,
                     best: int = 0,
                     mods=None,
                     mapid: int = 0,
                     isint: bool = False) -> Union[str, MessageSegment]:
    if mods is None:
        mods = []
    try:
        score_json = await osu_api(project, uid, mode, mapid, isint=isint)
        if not score_json:
            return '未查询到游玩记录'
        elif isinstance(score_json, str):
            return score_json
        score_info = ScoreInfo(score_json)
        if project == 'recent':
            score_info.recent_score()
        elif project == 'bp':
            score_info.bp_score(best, mods)
            if mods:
                if not score_info.mods_list:
                    return f'未找到开启 {"|".join(mods)} Mods的第{best}个成绩'
        elif project == 'score':
            score_info.map_score(mods)
        else:
            raise 'Project Error'

        mapJson = await osu_api('map', map_id=score_info.mapid)
        mapinfo = Beatmapset(mapJson)
        if project == 'bp' or project == 'recent':
            header = await osu_api('info', uid, isint=isint)
            score_info.headericon = header['cover_url']
            score_info.grank = '--'
        # 下载地图
        dirpath = await MapDownload(score_info.setid)
        osu = await OsuFileDl(score_info.mapid)
        # pp
        calc = PPCalc(score_info.mode, score_info.mapid)
        if score_info.mode == 0:
            _pp, ifpp, sspp, aim_pp, speed_pp, acc_pp, stars, ar, od = await calc.osu_pp(score_info.acc, score_info.maxcb,
                                                                                         score_info.c300, score_info.c100, score_info.c50,
                                                                                         score_info.cmiss, score_info.mods)
            pp = int(score_info.pp) if score_info.pp != -1 else _pp
        elif score_info.mode == 1:
            _pp, ifpp, stars = await calc.taiko_pp(score_info.acc, score_info.maxcb, score_info.c100, score_info.cmiss, score_info.mods)
            pp = int(score_info.pp) if score_info.pp != -1 else _pp
        elif score_info.mode == 2:
            _pp, ifpp, stars = await calc.catch_pp(score_info.acc, score_info.maxcb, score_info.cmiss, score_info.mods)
            pp = int(score_info.pp) if score_info.pp != -1 else _pp
        elif score_info.mode == 3:
            _pp, ifpp, stars = await calc.mania_pp(score_info.score, score_info.mods)
            pp = int(score_info.pp) if score_info.pp != -1 else _pp
        # 新建图片
        im = Image.new('RGBA', (1500, 800))
        # 获取cover并裁剪，高斯，降低亮度
        cover = re_map(osubytes(osu))
        if cover == 'mapbg.png':
            cover_path = os.path.join(osufile, 'work', cover)
        else:
            cover_path = os.path.join(dirpath, cover)
        cover_crop = crop_bg('BG', cover_path)
        cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(1))
        cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
        im.alpha_composite(cover_img, (0, 200))
        # 获取成绩背景做底图
        BG = get_modeimage(score_info.mode)
        recent_bg = Image.open(BG).convert('RGBA')
        im.alpha_composite(recent_bg)
        # 模式
        mode_bg = stars_diff(score_info.mode, stars)
        mode_img = mode_bg.resize((30, 30))
        im.alpha_composite(mode_img, (75, 154))
        # 难度星星
        stars_bg = stars_diff('stars', stars)
        stars_img = stars_bg.resize((23, 23))
        im.alpha_composite(stars_img, (134, 158))
        # mods
        if 'HD' in score_info.mods or 'FL' in score_info.mods:
            ranking = ['XH', 'SH', 'A', 'B', 'C', 'D', 'F']
        else:
            ranking = ['X', 'S', 'A', 'B', 'C', 'D', 'F']
        if score_info.mods:
            for mods_num, s_mods in enumerate(score_info.mods):
                mods_bg = os.path.join(osufile, 'mods', f'{s_mods}.png')
                mods_img = Image.open(mods_bg).convert('RGBA')
                im.alpha_composite(mods_img, (500 + 50 * mods_num, 240))
        # 成绩S-F
        rank_ok = False
        for rank_num, i in enumerate(ranking):
            rank_img = os.path.join(osufile, 'ranking', f'ranking-{i}.png')
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
        score_acc = wedge_acc(score_info.acc * 100)
        score_acc_bg = Image.open(score_acc).convert('RGBA').resize((576, 432))
        im.alpha_composite(score_acc_bg, (15, 153))
        # 获取头图，头像，地区，状态，support
        user_headericon = await get_projectimg(score_info.headericon)
        user_icon = await get_projectimg(score_info.icon_url)
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
        country = os.path.join(osufile, 'flags', f'{score_info.country_code}.png')
        country_bg = Image.open(country).convert('RGBA').resize((58, 39))
        im.alpha_composite(country_bg, (195, 606))
        # 在线状态
        status = os.path.join(osufile, 'work', 'on-line.png' if score_info.user_status else 'off-line.png')
        status_bg = Image.open(status).convert('RGBA').resize((45, 45))
        im.alpha_composite(status_bg, (114, 712))
        # supporter
        if score_info.supporter:
            supporter = os.path.join(osufile, 'work', 'suppoter.png')
            supporter_bg = Image.open(supporter).convert('RGBA').resize((40, 40))
            im.alpha_composite(supporter_bg, (267, 606))
        # cs, ar, od, hp, stardiff
        if score_info.mode == 0:
            mapdiff = [mapinfo.cs, mapinfo.hp, od, ar, stars]
        else:
            mapdiff = [mapinfo.cs, mapinfo.hp, mapinfo.od, mapinfo.ar, stars]
        for num, i in enumerate(mapdiff):
            color = (255, 255, 255, 255)
            if num == 4:
                color = (255, 204, 34, 255)
            difflen = int(250 * i / 10) if i <= 10 else 250
            diff_len = Image.new('RGBA', (difflen, 8), color)
            im.alpha_composite(diff_len, (1190, 386 + 35 * num))
            w_diff = datatext(1470, 386 + 35 * num, 20, i, Torus_SemiBold, anchor='mm')
            im = draw_text(im, w_diff)
        # 时长 - 滑条
        diffinfo = calc_songlen(mapinfo.total_len), mapinfo.bpm, mapinfo.c_circles, mapinfo.c_sliders
        for num, i in enumerate(diffinfo):
            w_info = datatext(1070 + 120 * num, 325, 20, i, Torus_Regular, anchor='lm')
            im = draw_text(im, w_info, (255, 204, 34, 255))
        # 状态
        w_status = datatext(1400, 264, 20, mapinfo.status.capitalize(), Torus_SemiBold, anchor='mm')
        im = draw_text(im, w_status)
        # mapid
        w_mapid = datatext(1425, 40, 27, f'Setid: {score_info.setid}  |  Mapid: {score_info.mapid}', Torus_SemiBold, anchor='rm')
        im = draw_text(im, w_mapid)
        # 曲名
        w_title = datatext(75, 118, 30, f'{mapinfo.title} | by {mapinfo.artist}', Meiryo_SemiBold, anchor='lm')
        im = draw_text(im, w_title)
        # 星级
        w_diff = datatext(162, 169, 18, stars, Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_diff)
        # 谱面版本，mapper
        w_version = datatext(225, 169, 22, f'{mapinfo.version} | mapper by {mapinfo.mapper}', Torus_SemiBold,
                             anchor='lm')
        im = draw_text(im, w_version)
        # 评价
        w_rank = datatext(309, 375, 75, score_info.rank, Venera, anchor='mm')
        im = draw_text(im, w_rank)
        # 分数
        w_score = datatext(498, 331, 75, f'{score_info.score:,}', Torus_Regular, anchor='lm')
        im = draw_text(im, w_score)
        # 玩家
        w_played = datatext(498, 396, 18, 'Played by:', Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_played)
        w_username = datatext(630, 396, 18, score_info.username, Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_username)
        # 时间
        w_date = datatext(498, 421, 18, 'Submitted on:', Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_date)
        old_time = datetime.strptime(score_info.date.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S')
        new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        w_time = datatext(630, 421, 18, new_time, Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_time)
        # 全球排名
        w_grank = datatext(513, 496, 24, score_info.grank, Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_grank)
        # 左下玩家名
        w_l_username = datatext(195, 670, 24, score_info.username, Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_l_username)
        # 在线，离线
        w_line = datatext(195, 732, 30, 'online' if score_info.user_status else 'offline', Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_line)
        # acc,cb,pp,300,100,50,miss
        if score_info.mode == 0:
            w_sspp = datatext(650, 625, 30, sspp, Torus_Regular, anchor='mm')
            im = draw_text(im, w_sspp)
            w_ifpp = datatext(770, 625, 30, ifpp, Torus_Regular, anchor='mm')
            im = draw_text(im, w_ifpp)
            w_pp = datatext(890, 625, 30, pp, Torus_Regular, anchor='mm')
            w_aimpp = datatext(650, 720, 30, aim_pp, Torus_Regular, anchor='mm')
            im = draw_text(im, w_aimpp)
            w_spdpp = datatext(770, 720, 30, speed_pp, Torus_Regular, anchor='mm')
            im = draw_text(im, w_spdpp)
            w_accpp = datatext(890, 720, 30, acc_pp, Torus_Regular, anchor='mm')
            im = draw_text(im, w_accpp)
            w_acc = datatext(1087, 625, 30, f'{score_info.acc * 100:.2f}%', Torus_Regular, anchor='mm')
            w_maxcb = datatext(1315, 625, 30, f'{score_info.maxcb:,}/{mapinfo.maxcb:,}', Torus_Regular, anchor='mm')
            w_300 = datatext(1030, 720, 30, score_info.c300, Torus_Regular, anchor='mm')
            w_100 = datatext(1144, 720, 30, score_info.c100, Torus_Regular, anchor='mm')
            w_50 = datatext(1258, 720, 30, score_info.c50, Torus_Regular, anchor='mm')
            im = draw_text(im, w_50)
            w_miss = datatext(1372, 720, 30, score_info.cmiss, Torus_Regular, anchor='mm')
        elif score_info.mode == 1:
            w_acc = datatext(1050, 625, 30, f'{score_info.acc * 100:.2f}%', Torus_Regular, anchor='mm')
            w_maxcb = datatext(1202, 625, 30, f'{score_info.maxcb:,}/{mapinfo.maxcb:,}', Torus_Regular, anchor='mm')
            w_pp = datatext(1352, 625, 30, f'{pp}/{ifpp}', Torus_Regular, anchor='mm')
            w_300 = datatext(1050, 720, 30, score_info.c300, Torus_Regular, anchor='mm')
            w_100 = datatext(1202, 720, 30, score_info.c100, Torus_Regular, anchor='mm')
            w_miss = datatext(1352, 720, 30, score_info.cmiss, Torus_Regular, anchor='mm')
        elif score_info.mode == 2:
            w_acc = datatext(1016, 625, 30, f'{score_info.acc * 100:.2f}%', Torus_Regular, anchor='mm')
            w_maxcb = datatext(1180, 625, 30, f'{score_info.maxcb:,}/{mapinfo.maxcb:,}', Torus_Regular, anchor='mm')
            w_pp = datatext(1344, 625, 30, f'{pp}/{ifpp}', Torus_Regular, anchor='mm')
            w_300 = datatext(995, 720, 30, score_info.c300, Torus_Regular, anchor='mm')
            w_100 = datatext(1118, 720, 30, score_info.c100, Torus_Regular, anchor='mm')
            w_katu = datatext(1242, 720, 30, score_info.ckatu, Torus_Regular, anchor='mm')
            im = draw_text(im, w_katu)
            w_miss = datatext(1365, 720, 30, score_info.cmiss, Torus_Regular, anchor='mm')
        else:
            w_acc = datatext(935, 625, 30, f'{score_info.acc * 100:.2f}%', Torus_Regular, anchor='mm')
            w_maxcb = datatext(1130, 625, 30, f'{score_info.maxcb:,}', Torus_Regular, anchor='mm')
            w_pp = datatext(1328, 625, 30, f'{pp}/{ifpp}', Torus_Regular, anchor='mm')
            w_geki = datatext(886, 720, 30, score_info.cgeki, Torus_Regular, anchor='mm')
            im = draw_text(im, w_geki)
            w_300 = datatext(984, 720, 30, score_info.c300, Torus_Regular, anchor='mm')
            w_katu = datatext(1083, 720, 30, score_info.ckatu, Torus_Regular, anchor='mm')
            im = draw_text(im, w_katu)
            w_100 = datatext(1182, 720, 30, score_info.c100, Torus_Regular, anchor='mm')
            w_50 = datatext(1280, 720, 30, score_info.c50, Torus_Regular, anchor='mm')
            im = draw_text(im, w_50)
            w_miss = datatext(1378, 720, 30, score_info.cmiss, Torus_Regular, anchor='mm')
        im = draw_text(im, w_acc)
        im = draw_text(im, w_maxcb)
        im = draw_text(im, w_pp)
        im = draw_text(im, w_300)
        im = draw_text(im, w_100)
        im = draw_text(im, w_miss)

        base = Tobase(im).image()
        msg = MessageSegment.image(base)
    except Exception as e:
        logger.error(f'制图错误：{traceback.print_exc()}')
        msg = f'Error: {type(e)}'
    return msg


def image_pfm(project: str, user: str, info: ScoreInfo, mode: str, min: int = 0, max: int = 0) -> Union[
    str, MessageSegment]:
    try:
        bplist_len = len(info.bpList)
        im = Image.new('RGBA', (1500, 180 + 82 * (bplist_len - 1)), (31, 41, 46, 255))
        bp_bg = os.path.join(osufile, 'Best Performance.png')
        BG_img = Image.open(bp_bg).convert('RGBA')
        im.alpha_composite(BG_img)
        f_div = Image.new('RGBA', (1500, 2), (255, 255, 255, 255)).convert('RGBA')
        im.alpha_composite(f_div, (0, 100))
        if project == 'bp':
            uinfo = f"{user}'s | {mode.capitalize()} | BP {min} - {max}"
        else:
            uinfo = f"{user}'s | {mode.capitalize()} | Today New BP"
        w_user = datatext(1450, 50, 25, uinfo, Torus_SemiBold, anchor='rm')
        im = draw_text(im, w_user)
        for num, bp in enumerate(info.bpList):
            h_num = 82 * num
            info.BestScore(bp)
            # mods
            if info.mods:
                for mods_num, s_mods in enumerate(info.mods):
                    mods_bg = os.path.join(osufile, 'mods', f'{s_mods}.png')
                    mods_img = Image.open(mods_bg).convert('RGBA')
                    im.alpha_composite(mods_img, (1000 + 50 * mods_num, 126 + h_num))
                if (info.rank == 'X' or info.rank == 'S') and ('HD' in info.mods or 'FL' in info.mods):
                    info.rank += 'H'
            # BP排名
            rank_bp = datatext(15, 144 + h_num, 20, bp + 1, Meiryo_Regular, anchor='lm')
            im = draw_text(im, rank_bp)
            # rank
            rank_img = os.path.join(osufile, 'ranking', f'ranking-{info.rank}.png')
            rank_bg = Image.open(rank_img).convert('RGBA').resize((64, 32))
            im.alpha_composite(rank_bg, (45, 128 + h_num))
            # 曲名&作曲
            w_title_artist = datatext(125, 130 + h_num, 20, f'{info.title} | by {info.artist}', Meiryo_Regular,
                                      anchor='lm')
            im = draw_text(im, w_title_artist)
            # 地图版本&时间
            old_time = datetime.strptime(info.date.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S')
            new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
            w_version_time = datatext(125, 158 + h_num, 18, f'{info.version} | {new_time}', Torus_Regular, anchor='lm')
            im = draw_text(im, w_version_time, color=(238, 171, 0, 255))
            # acc
            w_acc = datatext(1250, 130 + h_num, 22, f'{info.acc * 100:.2f}%', Torus_SemiBold, anchor='lm')
            im = draw_text(im, w_acc, color=(238, 171, 0, 255))
            # mapid
            w_mapid = datatext(1250, 158 + h_num, 18, f'ID: {info.mapid}', Torus_Regular, anchor='lm')
            im = draw_text(im, w_mapid)
            # pp
            w_pp = datatext(1420, 140 + h_num, 25, int(info.pp), Torus_SemiBold, anchor='rm')
            im = draw_text(im, w_pp, (255, 102, 171, 255))
            w_n_pp = datatext(1450, 140 + h_num, 25, 'pp', Torus_SemiBold, anchor='rm')
            im = draw_text(im, w_n_pp, (209, 148, 176, 255))
            # 分割线
            div = Image.new('RGBA', (1450, 2), (46, 53, 56, 255)).convert('RGBA')
            im.alpha_composite(div, (25, 180 + h_num))

        base = Tobase(im).image()
        msg = MessageSegment.image(base)
    except Exception as e:
        logger.error(f'制图错误：{traceback.print_exc()}')
        msg = f'Error: {type(e)}'
    return msg


async def best_pfm(project: str, id: Union[str, int], mode: str, min: int = 0, max: int = 0, mods: list = [],
                   isint: bool = False) -> Union[str, MessageSegment]:
    try:
        BPInfo = await osu_api('bp', id, mode, isint=isint)
        if isinstance(BPInfo, str):
            return BPInfo
        info = ScoreInfo(BPInfo)
        user = BPInfo[0]['user']['username']
        if project == 'bp':
            info.BestBPScore(min, max, mods)
            if isinstance(info.bpList, str):
                return info.bpList
            if mods and not info.mods_list:
                return f'未找到开启 {"|".join(mods)} Mods的成绩'
        elif project == 'tbp':
            info.new_bp_score()
            if not info.bpList:
                return f'今天没有新增的BP成绩'
        msg = image_pfm(project, user, info, mode, min, max)
    except Exception as e:
        logger.error(f'制图错误：{traceback.print_exc()}')
        msg = f'Error: {type(e)}'
    return msg


async def map_info(mapid: int, mods: list) -> Union[str, MessageSegment]:
    try:
        info = await osu_api('map', map_id=mapid)
        if not info:
            return '未查询到该地图信息'
        if isinstance(info, str):
            return info
        mapinfo = Beatmapset(info)
        diffinfo = calc_songlen(mapinfo.total_len), mapinfo.bpm, mapinfo.c_circles, mapinfo.c_sliders
        # 获取地图
        dirpath = await MapDownload(mapinfo.setid)
        osu = await OsuFileDl(mapid)
        # pp
        if mapinfo.mode == 0:
            pp, stars, ar, od = await PPCalc(mapinfo.mode, mapid).if_pp(mods=mods)
        else:
            pp, stars, _, _ = await PPCalc(mapinfo.mode, mapid).if_pp(mods=mods)
        # 计算时间
        if mapinfo.ranked_date:
            old_time = datetime.strptime(mapinfo.ranked_date.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S')
            new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            new_time = '??-??-?? ??:??:??'
        # BG做地图
        im = Image.new('RGBA', (1200, 600))
        cover = re_map(osubytes(osu))
        cover_crop = crop_bg('MB', os.path.join(dirpath, cover))
        cover_img = ImageEnhance.Brightness(cover_crop).enhance(2 / 4.0)
        im.alpha_composite(cover_img)
        # 获取地图info
        map_bg = os.path.join(osufile, 'beatmapinfo.png')
        mapbg = Image.open(map_bg).convert('RGBA')
        im.alpha_composite(mapbg)
        # 模式
        mode_bg = stars_diff(mapinfo.mode, stars)
        mode_img = mode_bg.resize((50, 50))
        im.alpha_composite(mode_img, (50, 100))
        # cs - diff
        if mapinfo.mode == 0:
            mapdiff = [mapinfo.cs, mapinfo.hp, od, ar, stars]
        else:
            mapdiff = [mapinfo.cs, mapinfo.hp, mapinfo.od, mapinfo.ar, stars]
        for num, i in enumerate(mapdiff):
            color = (255, 255, 255, 255)
            if num == 4:
                color = (255, 204, 34, 255)
            difflen = int(250 * i / 10) if i <= 10 else 250
            diff_len = Image.new('RGBA', (difflen, 8), color)
            im.alpha_composite(diff_len, (890, 426 + 35 * num))
            w_diff = datatext(1170, 426 + 35 * num, 20, i, Torus_SemiBold, anchor='mm')
            im = draw_text(im, w_diff)
        # mapper
        icon_url = f'https://a.ppy.sh/{mapinfo.uid}'
        user_icon = await get_projectimg(icon_url)
        icon = Image.open(user_icon).convert('RGBA').resize((100, 100))
        icon_img = draw_fillet(icon, 10)
        im.alpha_composite(icon_img, (50, 400))
        # mapid
        w_mapid = datatext(800, 40, 22, f'Setid: {mapinfo.setid}  |  Mapid: {mapid}', Torus_Regular, anchor='lm')
        im = draw_text(im, w_mapid)
        # 版本
        w_version = datatext(120, 125, 25, mapinfo.version, Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_version)
        # 曲名
        w_title = datatext(50, 170, 30, mapinfo.title, Meiryo_SemiBold)
        im = draw_text(im, w_title)
        # 曲师
        w_artist = datatext(50, 210, 25, f'by {mapinfo.artist}', Meiryo_SemiBold)
        im = draw_text(im, w_artist)
        # 来源
        w_source = datatext(50, 260, 25, f'Source:{mapinfo.source}', Meiryo_SemiBold)
        im = draw_text(im, w_source)
        # mapper
        w_mapper_by = datatext(160, 400, 20, 'mapper by:', Torus_SemiBold)
        im = draw_text(im, w_mapper_by)
        w_mapper = datatext(160, 425, 20, mapinfo.mapper, Torus_SemiBold)
        im = draw_text(im, w_mapper)
        # ranked时间
        w_time_by = datatext(160, 460, 20, 'ranked by:', Torus_SemiBold)
        im = draw_text(im, w_time_by)
        w_time = datatext(160, 485, 20, new_time, Torus_SemiBold)
        im = draw_text(im, w_time)
        # 状态
        w_status = datatext(1100, 304, 20, mapinfo.status.capitalize(), Torus_SemiBold, anchor='mm')
        im = draw_text(im, w_status)
        # 时长 - 滑条
        for num, i in enumerate(diffinfo):
            w_info = datatext(770 + 120 * num, 365, 20, i, Torus_Regular, anchor='lm')
            im = draw_text(im, w_info, (255, 204, 34, 255))
        # maxcb
        w_mapcb = datatext(50, 570, 20, f'Max Combo: {mapinfo.maxcb}', Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_mapcb)
        # pp
        w_pp = datatext(320, 570, 20, f'SS PP: {pp}', Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_pp)
        # 输出
        base = Tobase(im).image()
        msg = MessageSegment.image(base)
    except Exception as e:
        logger.error(f'制图错误：{traceback.print_exc()}')
        msg = f'Error:{type(e)}'
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
    if info['status'] == -1:
        return '未查询到地图'
    elif isinstance(info, str):
        return info
    try:
        songinfo = SayoInfo(info['data'])
        songinfo.map(info['data'])
        coverurl = f'https://assets.ppy.sh/beatmaps/{mapid}/covers/cover@2x.jpg'
        cover = await get_projectimg(coverurl)
        # 新建
        if len(songinfo.gmap) > 20:
            im_h = 400 + 102 * 20
        else:
            im_h = 400 + 102 * (len(songinfo.gmap) - 1)
        im = Image.new('RGBA', (1200, im_h), (31, 41, 46, 255))
        # 背景
        cover_crop = crop_bg('MP', cover)
        cover_gb = cover_crop.filter(ImageFilter.GaussianBlur(1))
        cover_img = ImageEnhance.Brightness(cover_gb).enhance(2 / 4.0)
        im.alpha_composite(cover_img, (0, 0))
        # 曲名
        w_title = datatext(25, 40, 38, songinfo.title, Meiryo_SemiBold)
        im = draw_text(im, w_title)
        # 曲师
        w_artist = datatext(25, 75, 20, f'by {songinfo.artist}', Meiryo_SemiBold)
        im = draw_text(im, w_artist)
        # mapper
        w_mapper = datatext(25, 110, 20, f'mapper by {songinfo.mapper}', Torus_SemiBold)
        im = draw_text(im, w_mapper)
        # rank时间
        if songinfo.apptime == -1:
            songinfo.apptime = '??-??-?? ??:??:??'
        else:
            datearray = datetime.utcfromtimestamp(songinfo.apptime)
            songinfo.apptime = (datearray + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        w_apptime = datatext(25, 145, 20, f'Approved Time: {songinfo.apptime}', Torus_SemiBold)
        im = draw_text(im, w_apptime)
        # 来源
        w_source = datatext(25, 180, 20, f'Source: {songinfo.source}', Meiryo_SemiBold)
        im = draw_text(im, w_source)
        # bpm
        w_bpm = datatext(1150, 110, 20, f'BPM: {songinfo.bpm}', Torus_SemiBold, anchor='rt')
        im = draw_text(im, w_bpm)
        # 曲长
        music_len = calc_songlen(songinfo.songlen)
        w_music_len = datatext(1150, 145, 20, f'lenght: {music_len}', Torus_SemiBold, anchor='rt')
        im = draw_text(im, w_music_len)
        # Setid
        w_setid = datatext(1150, 20, 20, f'Setid: {mapid}', Torus_SemiBold, anchor='rt')
        im = draw_text(im, w_setid)
        gmap = sorted(songinfo.gmap, key=lambda k: k['star'], reverse=False)
        for num, cmap in enumerate(gmap):
            if num < 20:
                h_num = 102 * num
                songinfo.mapinfo(cmap)
                # 难度
                mode_bg = stars_diff(songinfo.mode, songinfo.star)
                mode_img = mode_bg.resize((20, 20))
                im.alpha_composite(mode_img, (20, 320 + h_num))
                # 星星
                stars_bg = stars_diff('stars', songinfo.star)
                stars_img = stars_bg.resize((20, 20))
                im.alpha_composite(stars_img, (50, 320 + h_num))
                # diff
                bar_bg = os.path.join(osufile, 'work', 'bmap.png')
                bar_img = Image.open(bar_bg).convert('RGBA')
                im.alpha_composite(bar_img, (10, 365 + h_num))
                gc = ['CS', 'HP', 'OD', 'AR']
                for num, i in enumerate(songinfo.diff):
                    diff_len = int(200 * i / 10) if i <= 10 else 200
                    diff_bg = Image.new('RGBA', (diff_len, 12), (255, 255, 255, 255))
                    im.alpha_composite(diff_bg, (50 + 300 * num, 365 + h_num))
                    w_d_name = datatext(20 + 300 * num, 369 + h_num, 20, gc[num], Torus_SemiBold, anchor='lm')
                    im = draw_text(im, w_d_name)
                    w_diff = datatext(265 + 300 * num, 369 + h_num, 20, i, Torus_SemiBold, anchor='lm')
                    im = draw_text(im, w_diff, (255, 204, 34, 255))
                    if num != 3:
                        w_d = datatext(300 + 300 * num, 369 + h_num, 20, '|', Torus_SemiBold, anchor='lm')
                        im = draw_text(im, w_d)
                # 难度
                w_star = datatext(80, 328 + h_num, 20, songinfo.star, Torus_SemiBold, anchor='lm')
                im = draw_text(im, w_star)
                # version
                w_version = datatext(125, 328 + h_num, 20, f' |  {songinfo.version}', Torus_SemiBold, anchor='lm')
                im = draw_text(im, w_version)
                # mapid
                w_mapid = datatext(1150, 328 + h_num, 20, f'Mapid: {songinfo.bid}', Torus_SemiBold, anchor='rm')
                im = draw_text(im, w_mapid)
                # maxcb
                w_maxcb = datatext(700, 328 + h_num, 20, f'Max Combo: {songinfo.maxcb}', Torus_SemiBold, anchor='lm')
                im = draw_text(im, w_maxcb)
                # 分割线
                div = Image.new('RGBA', (1150, 2), (46, 53, 56, 255)).convert('RGBA')
                im.alpha_composite(div, (25, 400 + h_num))
            else:
                plusnum = f'+ {num - 19}'
        if num >= 20:
            w_plusnum = datatext(600, 350 + 102 * 20, 50, plusnum, Torus_SemiBold, anchor='mm')
            im = draw_text(im, w_plusnum)

        base = Tobase(im).image()
        msg = MessageSegment.image(base)
    except Exception as e:
        logger.error(f'制图错误：{traceback.print_exc()}')
        msg = f'Error: {type(e)}'
    return msg


async def bindinfo(project: str, id, qid) -> str:
    info = await osu_api(project, id, GM[0])
    if not info:
        return '未查询到该玩家'
    elif isinstance(info, str):
        return info
    uid = info['id']
    name = info['username']
    USER.insert_user(qid, uid, name)
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
    dirpath = await MapDownload(setid)
    osu = await OsuFileDl(mapid)
    path = re_map(osubytes(osu))
    msg = MessageSegment.image(f'file:///{os.path.join(dirpath, path)}')
    return msg


async def update_user_info(id: int, update: bool = False):
    for mode in range(0, 4):
        if not update:
            new = USER.get_info(id, mode)
            if new:
                continue
        userinfo = await osu_api('update', id, GM[mode], isint=True)
        if userinfo['statistics']['play_count'] != 0:
            info = UserInfo(userinfo)
            if update:
                USER.update_info(id, info.crank, info.grank, info.pp, round(info.acc, 2), info.play_count,
                                 info.play_hits, mode)
            else:
                USER.insert_info(id, info.crank, info.grank, info.pp, round(info.acc, 2), info.play_count,
                                 info.play_hits, mode)
        else:
            if update:
                USER.update_info(id, 0, 0, 0, 0, 0, 0, mode)
            else:
                USER.insert_info(id, 0, 0, 0, 0, 0, 0, mode)
        logger.info(f'玩家:[{userinfo["username"]}] {GM[mode]}模式 个人信息更新完毕')
