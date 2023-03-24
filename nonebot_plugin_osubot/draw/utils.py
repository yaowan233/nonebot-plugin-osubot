import math
import numpy as np
from io import BytesIO
from typing import Optional, Union
from PIL import ImageFont, ImageDraw

from .static import *


class DataText:
    # L=X轴，T=Y轴，size=字体大小，fontpath=字体文件，
    def __init__(self, length, height, size, text, path: Path, anchor='lt'):
        self.length = length
        self.height = height
        self.text = str(text)
        self.path = path
        self.font = ImageFont.truetype(str(self.path), size)
        self.anchor = anchor


def image2bytesio(pic: Image):
    byt = BytesIO()
    pic.save(byt, "png")
    return byt


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


def info_calc(n1: Optional[float], n2: Optional[float], rank: bool = False, pp: bool = False):
    if not n1 or not n2:
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


def draw_acc(img: Image, acc: float, mode: str):
    draw = ImageDraw.Draw(img)
    if mode == 'osu':
        size = [60, 20, 7, 7, 5, 1]
    elif mode == 'taiko':
        size = [60, 20, 5, 5, 4, 1]
    elif mode == 'fruits':
        size = [85, 5, 4, 4, 1, 1]
    else:
        size = [70, 10, 10, 5, 4, 1]
    start = -90
    color = ['#ff5858', '#ea7948', '#d99d03', '#72c904', '#0096a2', '#be0089']
    for s, c in zip(size, color):
        end = start + s / 100 * 360
        draw.arc((195, 183, 435, 423), start, end, fill=c, width=5)
        start = end
    draw.arc((165, 153, 465, 453), -90, -90 + 360 * acc, fill='#66cbfd', width=27)
    return img


def crop_bg(size: str, path: Union[str, BytesIO, Path]):
    bg = Image.open(path).convert('RGBA')
    bg_w, bg_h = bg.size[0], bg.size[1]
    if size == 'BG':
        fix_w = 1500
        fix_h = 720
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
    r, g, b = ColorPic[x, 1]
    # 打开底图
    im = Image.open(osufile / 'work' / f'{mode}.png').convert('RGBA')
    xx, yy = im.size
    # 填充背景
    sm = Image.new('RGBA', im.size, (r, g, b))
    sm.paste(im, (0, 0, xx, yy), im)
    # 把白色变透明
    arr = np.array(sm)
    # 创建mask，将白色替换为True，其他颜色替换为False
    mask = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 255) & (arr[:, :, 2] == 255)
    # 将mask中为True的像素点的alpha通道设置为0
    arr[:, :, 3][mask] = 0
    # 将numpy数组转换回PIL图片
    img = Image.fromarray(arr)
    return img


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
