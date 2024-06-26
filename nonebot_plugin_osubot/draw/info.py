import asyncio
from datetime import datetime, timedelta, date
from io import BytesIO
from typing import Union

from PIL import ImageDraw, ImageSequence, UnidentifiedImageError

from .static import (
    Image,
    Torus_Regular_20,
    ExpLeftBg,
    ExpRightBg,
    ExpCenterBg,
    Torus_Regular_45,
    Torus_Regular_40,
    Torus_Regular_30,
    Torus_Regular_25,
    Torus_Regular_35,
    SupporterBg,
    osufile,
    Torus_Regular_50,
    InfoImg,
)
from .utils import draw_fillet, info_calc, open_user_icon, update_icon
from ..api import osu_api, get_random_bg
from ..database.models import InfoData
from ..file import make_badge_cache_file, user_cache_path, badge_cache_path
from ..schema import User
from ..utils import GMN, FGM


async def draw_info(
    uid: Union[int, str], mode: str, day: int, is_name
) -> Union[str, BytesIO]:
    info_json = await osu_api("info", uid, mode, is_name=is_name)
    if isinstance(info_json, str):
        return info_json
    info = User(**info_json)
    statistics = info.statistics
    if statistics.play_count == 0:
        return f"此玩家尚未游玩过{GMN[mode]}模式"
    # 对比
    user = (
        await InfoData.filter(osu_id=info.id, osu_mode=FGM[mode])
        .order_by("-date")
        .first()
    )
    if user:
        today_date = date.today()
        query_date = today_date - timedelta(days=day)
        if (
            user := await InfoData.filter(
                osu_id=info.id, osu_mode=FGM[mode], date__gte=query_date
            )
            .order_by("date")
            .first()
        ):
            n_crank, n_grank, n_pp, n_acc, n_pc, n_count = (
                user.c_rank,
                user.g_rank,
                user.pp,
                user.acc,
                user.pc,
                user.count,
            )
        else:
            n_crank, n_grank, n_pp, n_acc, n_pc, n_count = (
                statistics.country_rank,
                statistics.global_rank,
                statistics.pp,
                statistics.hit_accuracy,
                statistics.play_count,
                statistics.total_hits,
            )
    else:
        n_crank, n_grank, n_pp, n_acc, n_pc, n_count = (
            statistics.country_rank,
            statistics.global_rank,
            statistics.pp,
            statistics.hit_accuracy,
            statistics.play_count,
            statistics.total_hits,
        )
    # 新建
    im = Image.new("RGBA", (1000, 1350))
    draw = ImageDraw.Draw(im)
    # 获取背景
    bg_path = user_cache_path / str(info.id) / "info.png"
    if bg_path.exists():
        try:
            bg = Image.open(bg_path)
        except UnidentifiedImageError:
            bg_path.unlink()
            return "自定义背景图片读取错误，请重新上传！"
    else:
        bg = await get_random_bg()
        if bg:
            bg = Image.open(BytesIO(bg))
    if bg:
        bg = bg.convert("RGBA")
        width, height = bg.size
        bg_ratio = height / width
        ratio = 1350 / 1000
        if bg_ratio > ratio:
            height = ratio * width
        else:
            width = height / ratio
        x, y = bg.size
        x, y = (x - width) // 2, (y - height) // 2
        bg = bg.crop((x, y, x + width, y + height)).resize((1000, 1350))
        im.alpha_composite(bg, (0, 0))
    # 获取头图，头像，地区，状态，supporter
    path = user_cache_path / str(info.id)
    if not path.exists():
        path.mkdir()
    country = osufile / "flags" / f"{info.country_code}.png"
    # 底图
    im.alpha_composite(InfoImg)
    # 奖牌
    if info.badges:
        badges_num = len(info.badges)
        for num, badge in enumerate(info.badges):
            if badges_num <= 9:
                length = 50 + 100 * num
                height = 510
            elif num < 9:
                length = 50 + 100 * num
                height = 486
            else:
                length = 50 + 100 * (num - 9)
                height = 534
            badges_path = badge_cache_path / f"{hash(badge.description)}.png"
            if not badges_path.exists():
                await make_badge_cache_file(badge)
            try:
                badges_img = Image.open(badges_path).convert("RGBA").resize((86, 40))
            except UnidentifiedImageError:
                badges_path.unlink()
                return "图片下载错误，请重试！"
            im.alpha_composite(badges_img, (length, height))
    # 地区
    country_bg = Image.open(country).convert("RGBA").resize((80, 54))
    im.alpha_composite(country_bg, (400, 394))
    # supporter
    if info.is_supporter:
        im.alpha_composite(SupporterBg.resize((54, 54)), (400, 280))
    # 经验
    if statistics.level.progress != 0:
        im.alpha_composite(ExpLeftBg, (50, 646))
        exp_width = statistics.level.progress * 7 - 3
        im.alpha_composite(ExpCenterBg.resize((exp_width, 10)), (54, 646))
        im.alpha_composite(ExpRightBg, (int(54 + exp_width), 646))
    # 模式
    draw.text((935, 50), GMN[mode], font=Torus_Regular_45, anchor="rm")
    # 玩家名
    draw.text((400, 205), info.username, font=Torus_Regular_50, anchor="lm")
    # 地区排名
    op, value = info_calc(statistics.country_rank, n_crank, rank=True)
    if not statistics.country_rank:
        t_crank = "#0"
    else:
        t_crank = (
            f"#{statistics.country_rank:,}({op}{value:,})"
            if value != 0
            else f"#{statistics.country_rank:,}"
        )
    draw.text((495, 448), t_crank, font=Torus_Regular_30, anchor="lb")
    # 等级
    draw.text(
        (900, 650), str(statistics.level.current), font=Torus_Regular_25, anchor="mm"
    )
    # 经验百分比
    draw.text(
        (750, 660), f"{statistics.level.progress}%", font=Torus_Regular_20, anchor="rt"
    )
    # 全球排名
    if not statistics.global_rank:
        draw.text((55, 785), "#0", font=Torus_Regular_35, anchor="lt")
    else:
        draw.text(
            (55, 785),
            f"#{statistics.global_rank:,}",
            font=Torus_Regular_35,
            anchor="lt",
        )
    op, value = info_calc(statistics.global_rank, n_grank, rank=True)
    if value != 0:
        draw.text((65, 820), f"{op}{value:,}", font=Torus_Regular_20, anchor="lt")
    # pp
    draw.text((295, 785), f"{statistics.pp:,}", font=Torus_Regular_35, anchor="lt")
    op, value = info_calc(statistics.pp, n_pp, pp=True)
    if value != 0:
        draw.text((305, 820), f"{op}{int(value)}", font=Torus_Regular_20)
    # SS - A
    # gc_x = 493
    for gc_num, (_, num) in enumerate(statistics.grade_counts):
        draw.text(
            (493 + 100 * gc_num, 788), f"{num}", font=Torus_Regular_30, anchor="mt"
        )
        # gc_x+=100
    # rank分
    draw.text(
        (935, 895), f"{statistics.ranked_score:,}", font=Torus_Regular_40, anchor="rt"
    )
    # acc
    op, value = info_calc(statistics.hit_accuracy, n_acc)
    t_acc = (
        f"{statistics.hit_accuracy:.2f}%({op}{value:.2f}%)"
        if value != 0
        else f"{statistics.hit_accuracy:.2f}%"
    )
    draw.text((935, 965), t_acc, font=Torus_Regular_40, anchor="rt")
    # 游玩次数
    op, value = info_calc(statistics.play_count, n_pc)
    t_pc = (
        f"{statistics.play_count:,}({op}{value:,})"
        if value != 0
        else f"{statistics.play_count:,}"
    )
    draw.text((935, 1035), t_pc, font=Torus_Regular_40, anchor="rt")
    # 总分
    draw.text(
        (935, 1105), f"{statistics.total_score:,}", font=Torus_Regular_40, anchor="rt"
    )
    # 总命中
    op, value = info_calc(statistics.total_hits, n_count)
    t_count = (
        f"{statistics.total_hits:,}({op}{value:,})"
        if value != 0
        else f"{statistics.total_hits:,}"
    )
    draw.text((935, 1175), t_count, font=Torus_Regular_40, anchor="rt")
    # 游玩时间
    sec = timedelta(seconds=statistics.play_time)
    d_time = datetime(1, 1, 1) + sec
    t_time = "%dd %dh %dm %ds" % (sec.days, d_time.hour, d_time.minute, d_time.second)
    draw.text((935, 1245), t_time, font=Torus_Regular_40, anchor="rt")
    # 底部时间对比
    if day != 0 and user:
        day_delta = date.today() - user.date
        time = day_delta.days
        current_time = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        draw.text((260, 1305), current_time, font=Torus_Regular_25, anchor="la")
        text = f"| 数据对比于 {time} 天前"
        draw.text((515, 1305), text, font=Torus_Regular_25, anchor="la")
    else:
        current_time = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        draw.text((380, 1305), current_time, font=Torus_Regular_25, anchor="la")
    # 头像
    gif_frames = []
    user_icon = await open_user_icon(info)
    _ = asyncio.create_task(update_icon(info))
    if not getattr(user_icon, "is_animated", False):
        icon_bg = user_icon.convert("RGBA").resize((300, 300))
        icon_img = draw_fillet(icon_bg, 25)
        im.alpha_composite(icon_img, (50, 148))
        byt = BytesIO()
        im.convert("RGB").save(byt, "jpeg")
        im.close()
        user_icon.close()
        return byt
    for gif_frame in ImageSequence.Iterator(user_icon):
        # 将 GIF 图片中的每一帧转换为 RGBA 模式
        gif_frame = gif_frame.convert("RGBA").resize((300, 300))
        gif_frame = draw_fillet(gif_frame, 25)
        # 创建一个新的 RGBA 图片，将 PNG 图片作为背景，将当前帧添加到背景上
        rgba_frame = Image.new("RGBA", im.size, (0, 0, 0, 0))
        rgba_frame.paste(im, (0, 0), im)
        rgba_frame.paste(gif_frame, (50, 148), gif_frame)
        # 将 RGBA 图片转换为 RGB 模式，并添加到 GIF 图片中
        gif_frames.append(rgba_frame)
    gif_bytes = BytesIO()
    # 保存 GIF 图片
    gif_frames[0].save(
        gif_bytes,
        format="gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=user_icon.info["duration"],
    )
    # 输出
    gif_frames[0].close()
    user_icon.close()
    return gif_bytes
