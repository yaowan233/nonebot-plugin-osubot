import os
import random

from io import BytesIO
from typing import Optional, Union
from PIL import ImageDraw, UnidentifiedImageError, ImageEnhance, ImageFilter
from matplotlib.figure import Figure

from ..file import get_projectimg, user_cache_path
from ..schema import SeasonalBackgrounds, User
from ..api import get_seasonal_bg, safe_async_get

from .static import *


def image2bytesio(pic: Image):
    byt = BytesIO()
    pic.save(byt, "png")
    return byt


def draw_fillet(img, radii):
    # 画圆（用于分离4个角）
    circle = Image.new("L", (radii * 2, radii * 2), 0)  # 创建一个黑色背景的画布
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radii * 2, radii * 2), fill=255)  # 画白色圆形
    # 原图
    img = img.convert("RGBA")
    w, h = img.size
    # 画4个角（将整圆分离为4个部分）
    alpha = Image.new("L", img.size, 255)
    alpha.paste(circle.crop((0, 0, radii, radii)), (0, 0))  # 左上角
    alpha.paste(circle.crop((radii, 0, radii * 2, radii)), (w - radii, 0))  # 右上角
    alpha.paste(
        circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii)
    )  # 右下角
    alpha.paste(circle.crop((0, radii, radii, radii * 2)), (0, h - radii))  # 左下角
    # 白色区域透明可见，黑色区域不可见
    img.putalpha(alpha)
    return img


def draw_fillet2(img, radii):
    # 画圆（用于分离4个角）
    circle = Image.new("L", (radii * 2, radii * 2), 0)  # 创建一个黑色背景的画布
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radii * 2, radii * 2), fill=255)  # 画白色圆形
    # 原图
    img = img.convert("RGBA")
    w, h = img.size
    # 创建一个透明度为50%的图像
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.5)
    # 画4个角（将整圆分离为4个部分）
    alpha = Image.new("L", img.size, 255)
    alpha.paste(circle.crop((0, 0, radii, radii)), (0, 0))  # 左上角
    alpha.paste(circle.crop((radii, 0, radii * 2, radii)), (w - radii, 0))  # 右上角
    alpha.paste(
        circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii)
    )  # 右下角
    alpha.paste(circle.crop((0, radii, radii, radii * 2)), (0, h - radii))  # 左下角
    # 高斯模糊效果
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    # 白色区域透明可见，黑色区域不可见
    img.putalpha(alpha)
    return img


def info_calc(
    n1: Optional[float], n2: Optional[float], rank: bool = False, pp: bool = False
):
    if not n1 or not n2:
        return "", 0
    num = n1 - n2
    if num < 0:
        if rank:
            op, value = "↑", num * -1
        elif pp:
            op, value = "↓", num * -1
        else:
            op, value = "-", num * -1
    elif num > 0:
        if rank:
            op, value = "↓", num
        elif pp:
            op, value = "↑", num
        else:
            op, value = "+", num
    else:
        op, value = "", 0
    return [op, value]


def draw_acc(img: Image, acc: float, mode: int):
    acc *= 100
    size = [acc, 100 - acc]
    if mode == 0:
        insize = [60, 20, 7, 7, 5, 1]
    elif mode == 1:
        insize = [60, 20, 5, 5, 4, 1]
    elif mode == 2:
        insize = [85, 5, 4, 4, 1, 1]
    else:
        insize = [70, 10, 10, 5, 4, 1]
    insizecolor = ["#ff5858", "#ea7948", "#d99d03", "#72c904", "#0096a2", "#be0089"]
    fig = Figure()
    ax = fig.add_axes((0.1, 0.1, 0.8, 0.8))
    patches = ax.pie(
        size,
        radius=1,
        startangle=90,
        counterclock=False,
        pctdistance=0.9,
        wedgeprops=dict(width=0.20),
        colors=["#66cbfd"],
    )
    ax.pie(
        insize,
        radius=0.8,
        colors=insizecolor,
        startangle=90,
        counterclock=False,
        pctdistance=0.9,
        wedgeprops=dict(width=0.05),
    )
    patches[0][1].set_alpha(0)
    acc_img = BytesIO()
    fig.savefig(acc_img, transparent=True)
    ax.cla()
    ax.clear()
    fig.clf()
    fig.clear()
    score_acc_img = Image.open(acc_img).convert("RGBA").resize((576, 432))
    img.alpha_composite(score_acc_img, (25, 83))
    return img


async def crop_bg(size: str, path: Union[str, Path, BytesIO]):
    try:
        bg = Image.open(path).convert("RGBA")
    except UnidentifiedImageError:
        os.remove(path)
        data = await get_seasonal_bg()
        pic = SeasonalBackgrounds(**data)
        url = random.choice(pic.backgrounds).url
        res = await safe_async_get(url)
        bg = Image.open(BytesIO(res.content)).convert("RGBA")
    except FileNotFoundError:
        data = await get_seasonal_bg()
        pic = SeasonalBackgrounds(**data)
        url = random.choice(pic.backgrounds).url
        res = await safe_async_get(url)
        bg = Image.open(BytesIO(res.content)).convert("RGBA")
    bg_w, bg_h = bg.size[0], bg.size[1]
    if size == "BG":
        fix_w = 1500
        fix_h = 720
    elif size == "H":
        fix_w = 540
        fix_h = 180
    elif size == "HI":
        fix_w = 1000
        fix_h = 400
    elif size == "MP":
        fix_w = 1200
        fix_h = 300
    elif size == "MB":
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
        crop_height = (height - fix_h) // 2
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
        crop_width = (width - fix_w) // 2
        x1, y1, x2, y2 = crop_width, 0, width - crop_width, height
        # 裁切保存
        crop_img = sf.crop((x1, y1, x2, y2))
        return crop_img
    else:
        sf = bg.resize((fix_w, fix_h))
        return sf


def stars_diff(stars: float):
    if stars < 0.1:
        r, g, b = 170, 170, 170
    elif stars >= 9:
        r, g, b = 0, 0, 0
    else:
        # 颜色取色参考 https://github.com/ppy/osu-web/blob/97997d9c7b7f9c49f9b3cdd776c71afb9872c34b/resources/js/utils/beatmap-helper.ts#L20
        r, g, b, a = ColorArr[int(stars * 100)]
    # 打开底图
    xx, yy = Stars.size
    # 填充背景
    img = Image.new("RGBA", Stars.size, (r, g, b))
    img.paste(Stars, (0, 0, xx, yy), Stars)
    # 把白色变透明
    arr = np.array(img)
    # 创建mask，将白色替换为True，其他颜色替换为False
    mask = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 255) & (arr[:, :, 2] == 255)
    # 将mask中为True的像素点的alpha通道设置为0
    arr[:, :, 3][mask] = 0
    # 将numpy数组转换回PIL图片
    img = Image.fromarray(arr)
    return img


def get_modeimage(mode: int) -> Path:
    if mode == 0:
        img = "pfm_std.png"
    elif mode == 1:
        img = "pfm_taiko.png"
    elif mode == 2:
        img = "pfm_ctb.png"
    else:
        img = "pfm_mania.png"
    return osufile / img


def calc_songlen(length: int) -> str:
    map_len = list(divmod(int(length), 60))
    map_len[1] = map_len[1] if map_len[1] >= 10 else f"0{map_len[1]}"
    music_len = f"{map_len[0]}:{map_len[1]}"
    return music_len


async def open_user_icon(info: User) -> Image:
    path = user_cache_path / str(info.id)
    png_user_icon = user_cache_path / str(info.id) / "icon.png"
    gif_user_icon = user_cache_path / str(info.id) / "icon.gif"
    # 判断文件是否存在，并读取图片
    if png_user_icon.exists():
        image = Image.open(png_user_icon)
    elif gif_user_icon.exists():
        image = Image.open(gif_user_icon)
    else:
        user_icon = await get_projectimg(info.avatar_url)
        with open(path / f"icon.{info.avatar_url[-3:]}", "wb") as f:
            f.write(user_icon.getvalue())
        image = Image.open(user_icon)
    return image


def is_close(n1, n2) -> bool:
    if abs(n1 - n2) < 0.01:
        return True
    return False
