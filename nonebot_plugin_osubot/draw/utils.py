import os
import re
import random
import datetime
from io import BytesIO
from typing import Union, Optional
from difflib import SequenceMatcher

from PIL.ImageFile import ImageFile
from matplotlib.figure import Figure
from PIL import ImageDraw, ImageFilter, ImageEnhance, UnidentifiedImageError

from ..schema.user import UnifiedUser
from ..schema import SeasonalBackgrounds
from ..api import safe_async_get, get_seasonal_bg
from .static import Path, Image, ColorArr, np, osufile
from ..file import map_path, download_osu, get_projectimg, user_cache_path, team_cache_path


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
    alpha.paste(circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii))  # 右下角
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
    alpha.paste(circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii))  # 右下角
    alpha.paste(circle.crop((0, radii, radii, radii * 2)), (0, h - radii))  # 左下角
    # 高斯模糊效果
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    # 白色区域透明可见，黑色区域不可见
    img.putalpha(alpha)
    return img


def info_calc(n1: Optional[float], n2: Optional[float], rank: bool = False, pp: bool = False):
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
    size = [acc, 100 - acc]
    if mode == 0:
        insize = [60, 20, 7, 7, 5, 1]
    elif mode == 1:
        insize = [60, 15, 8, 8, 8, 1]
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
        wedgeprops={"width": 0.20},
        colors=["#66cbfd"],
    )
    ax.pie(
        insize,
        radius=0.8,
        colors=insizecolor,
        startangle=90,
        counterclock=False,
        pctdistance=0.9,
        wedgeprops={"width": 0.05},
    )
    patches[0][1].set_alpha(0)
    acc_img = BytesIO()
    fig.savefig(acc_img, transparent=True)
    ax.cla()
    ax.clear()
    fig.clf()
    fig.clear()
    score_acc_img = Image.open(acc_img).convert("RGBA").resize((384, 288))
    img.alpha_composite(score_acc_img, (580, 35))
    return img


async def crop_bg(size: tuple[int, int], path: Union[str, Path, BytesIO, Image.Image]):
    if not isinstance(path, Image.Image):
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
    else:
        bg = path
    bg_w, bg_h = bg.size[0], bg.size[1]
    fix_w, fix_h = size[0], size[1]
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


def stars_diff(stars: float, stars_bg: ImageFile):
    if stars < 0.1:
        r, g, b = 170, 170, 170
    elif stars >= 9:
        r, g, b = 0, 0, 0
    else:
        # 颜色取色参考 https://github.com/ppy/osu-web/blob/97997d9c7b7f9c49f9b3cdd776c71afb9872c34b/resources/js/utils/beatmap-helper.ts#L20
        r, g, b, _a = ColorArr[int(stars * 100)]
    # 打开底图
    xx, yy = stars_bg.size
    # 填充背景
    img = Image.new("RGBA", stars_bg.size, (r, g, b))
    img.paste(stars_bg, (0, 0, xx, yy), stars_bg)
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
    if mode in {0, 4, 8}:
        img = "pfm_std.png"
    elif mode in {1, 5}:
        img = "pfm_taiko.png"
    elif mode in {2, 6}:
        img = "pfm_ctb.png"
    else:
        img = "pfm_mania.png"
    return osufile / img


def calc_songlen(length: int) -> str:
    map_len = list(divmod(int(length), 60))
    map_len[1] = map_len[1] if map_len[1] >= 10 else f"0{map_len[1]}"
    music_len = f"{map_len[0]}:{map_len[1]}"
    return music_len


async def open_user_icon(info: UnifiedUser, source) -> Image:
    path = user_cache_path / str(info.id)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    for file_path in path.glob("icon*.*"):
        # 检查文件是否为图片格式
        if file_path.suffix.lower() in [".jpg", ".png", ".jpeg", ".gif", ".bmp"]:
            img = Image.open(file_path)
            break
    else:
        user_icon = await get_projectimg(info.avatar_url)
        if source == "ppysb":
            with open(path / "sb_icon.png", "wb") as f:
                f.write(user_icon.getvalue())
        else:
            with open(path / f"icon.{info.avatar_url.split('.')[-1]}", "wb") as f:
                f.write(user_icon.getvalue())
        img = Image.open(user_icon)
    return img


def is_close(n1, n2) -> bool:
    if abs(n1 - n2) < 0.01:
        return True
    return False


async def update_icon(info: UnifiedUser):
    path = user_cache_path / str(info.id)
    for file_path in path.glob("icon*.*"):
        # 检查文件是否为图片格式
        if file_path.suffix.lower() in [".jpg", ".png", ".jpeg", ".gif", ".bmp"]:
            modified_time = file_path.stat().st_mtime
            modified_datetime = datetime.datetime.fromtimestamp(modified_time)
            time_diff = datetime.datetime.now() - modified_datetime
            # 判断文件是否创建超过一天
            if time_diff > datetime.timedelta(days=1):
                file_path.unlink()
                user_icon = await get_projectimg(info.avatar_url)
                with open(path / f"icon.{info.avatar_url.split('.')[-1]}", "wb") as f:
                    f.write(user_icon.getvalue())
    if info.team:
        team_path = team_cache_path / f"{info.team.id}.png"
        if team_path.exists():
            modified_time = team_path.stat().st_mtime
            modified_datetime = datetime.datetime.fromtimestamp(modified_time)
            time_diff = datetime.datetime.now() - modified_datetime
            # 判断文件是否创建超过一天
            if time_diff > datetime.timedelta(days=1):
                team_path.unlink()
                team_icon = await get_projectimg(info.team.flag_url)
                with open(team_path, "wb") as f:
                    f.write(team_icon.getvalue())


async def update_map(set_id, map_id):
    path = map_path / str(set_id)
    for file_path in path.glob("*.osu"):
        # 检查文件是否为图片格式
        modified_time = file_path.stat().st_mtime
        modified_datetime = datetime.datetime.fromtimestamp(modified_time)
        time_diff = datetime.datetime.now() - modified_datetime
        # 判断文件是否创建超过一天
        if time_diff > datetime.timedelta(days=1):
            await download_osu(set_id, map_id)


def draw_rounded_rectangle(
    draw: ImageDraw.Draw, xy: tuple[tuple[int, int], tuple[int, int]], corner_radius: int, fill: str = None
) -> None:
    upper_left_point = xy[0]
    bottom_right_point = xy[1]

    # 计算矩形的四个角的坐标
    top_left = (upper_left_point[0], upper_left_point[1])
    top_right = (bottom_right_point[0], upper_left_point[1])
    bottom_left = (upper_left_point[0], bottom_right_point[1])
    bottom_right = (bottom_right_point[0], bottom_right_point[1])

    # 绘制四个角的四分之一圆
    draw.pieslice(
        [top_left, (top_left[0] + corner_radius * 2, top_left[1] + corner_radius * 2)], start=180, end=270, fill=fill
    )
    draw.pieslice(
        [(top_right[0] - corner_radius * 2, top_right[1]), (top_right[0], top_right[1] + corner_radius * 2)],
        start=270,
        end=360,
        fill=fill,
    )
    draw.pieslice(
        [(bottom_left[0], bottom_left[1] - corner_radius * 2), (bottom_left[0] + corner_radius * 2, bottom_left[1])],
        start=90,
        end=180,
        fill=fill,
    )
    draw.pieslice(
        [
            (bottom_right[0] - corner_radius * 2, bottom_right[1] - corner_radius * 2),
            (bottom_right[0], bottom_right[1]),
        ],
        start=0,
        end=90,
        fill=fill,
    )

    # 绘制矩形填充四个圆角之间的空间
    draw.rectangle(
        [top_left[0] + corner_radius, top_left[1], bottom_right[0] - corner_radius, bottom_right[1]], fill=fill
    )
    draw.rectangle(
        [top_left[0], top_left[1] + corner_radius, bottom_right[0], bottom_right[1] - corner_radius], fill=fill
    )


map_dict = {
    "mapper": "creator",
    "length": "total_length",
    "acc": "accuracy",
    "hp": "drain",
    "star": "difficulty_rating",
    "combo": "max_combo",
    "keys": "cs",
}


def matches_condition_with_regex(score, key, operator, value):
    """
    匹配条件，支持正则与模糊搜索。
    """
    key = map_dict.get(key, key)
    beatmap = getattr(score, "beatmap", None)
    beatmapset = getattr(score, "beatmapset", None)
    statistics = getattr(score, "statistics", None)
    attr = getattr(score, key, None)
    attr1 = getattr(beatmap, key, None)
    attr2 = getattr(beatmapset, key, None)
    attr3 = getattr(statistics, key, None)
    if not bool(attr or attr1 or attr2 or attr3):
        return False
    if not attr and attr1:
        attr = attr1
    if not attr and attr2:
        attr = attr2
    if not attr and attr3:
        attr = attr3
    if key == "accuracy":
        attr = float(attr)
    # 正则和模糊匹配
    if isinstance(attr, str):
        if operator == "=":
            return attr.lower() == value.lower()
        elif operator == "!=":
            return attr.lower() != value.lower()
        elif operator == "~":  # 正则匹配
            return re.search(value, attr, re.IGNORECASE) is not None
        elif operator == "~=":  # 模糊匹配
            return SequenceMatcher(None, attr.lower(), value.lower()).ratio() >= 0.5

    # 数值比较
    elif isinstance(attr, (int, float)):
        value = float(value)
        if operator == ">":
            return attr > value
        elif operator == "<":
            return attr < value
        elif operator == ">=":
            return attr >= value
        elif operator == "<=":
            return attr <= value
        elif operator == "=":
            return attr == value

    return False


def filter_scores_with_regex(scores_with_index, conditions):
    """
    根据动态条件过滤分数列表，支持正则与模糊搜索。
    """
    for key, operator, value in conditions:
        scores_with_index = [
            score for score in scores_with_index if matches_condition_with_regex(score, key, operator, value)
        ]
    return scores_with_index


def trim_text_with_ellipsis(text, max_width, font):
    # 初始检查：空字符串或无需处理
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    if not text or text_width <= max_width:
        return text
    # 逐字符检查
    ellipsis_symbol = "…"
    ellipsis_width = font.getbbox("…")[2] - font.getbbox("…")[0]
    # 确保最大宽度能至少容纳一个字符+省略号
    if max_width < font.getbbox("A")[2] - font.getbbox("A")[0] + ellipsis_width:
        return ellipsis_symbol

    truncated_text = ""
    current_width = 0

    for char in text:
        # 检查当前字符宽度 + 省略号宽度是否超标
        char_width = font.getbbox(char)[2] - font.getbbox(char)[0]
        if current_width + char_width + ellipsis_width > max_width:
            break
        truncated_text += char
        current_width += char_width

    # 返回截断后的字符串 + 省略号
    return truncated_text + ellipsis_symbol if truncated_text else ellipsis_symbol


# 字体描边函数
def draw_text_with_outline(draw, position, text, font, anchor, fill):
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx != 0 or dy != 0:
                draw.text(
                    (position[0] + dx, position[1] + dy),
                    text,
                    font=font,
                    anchor=anchor,
                    fill=(0, 0, 0, 255),
                )
    draw.text(position, text, font=font, anchor=anchor, fill=fill)
