import base64
import jinja2
from pathlib import Path
from typing import Union
from datetime import date, datetime, timedelta

from PIL import UnidentifiedImageError
from nonebot_plugin_htmlrender import get_new_page

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from .utils import info_calc
from ..utils import FGM, GMN
from ..file import user_cache_path, get_projectimg
from ..exceptions import NetworkError
from ..database.models import InfoData
from ..schema.draw_info import DrawUser, Badge
from ..api import get_random_bg, get_user_info_data


async def draw_info(uid: Union[int, str], mode: str, day: int, source: str) -> bytes:
    info = await get_user_info_data(uid, mode, source)
    statistics = info.statistics
    if statistics.play_count == 0:
        raise NetworkError(f"此玩家尚未游玩过{GMN[mode]}模式")
    # 对比
    async with get_session() as session:
        user = await session.scalar(
            select(InfoData)
            .where(InfoData.osu_id == info.id, InfoData.osu_mode == FGM[mode])
            .order_by(InfoData.date.desc())
        )
        if user:
            today_date = date.today()
            # 补全今天记录的 c_rank（批量更新接口不返回 country_rank）
            today_record = await session.scalar(
                select(InfoData).where(
                    InfoData.osu_id == info.id, InfoData.osu_mode == FGM[mode], InfoData.date == today_date
                )
            )
            if today_record and today_record.c_rank is None and statistics.country_rank is not None:
                today_record.c_rank = statistics.country_rank
                await session.commit()
            query_date = today_date - timedelta(days=day)
            user = await session.scalar(
                select(InfoData)
                .where(InfoData.osu_id == info.id, InfoData.osu_mode == FGM[mode], InfoData.date >= query_date)
                .order_by(InfoData.date)
            )
    if user:
        n_crank = user.c_rank
        n_grank = user.g_rank
        n_pp = user.pp
        n_acc = user.acc
        n_pc = user.pc
        n_count = user.count
        n_ranked_score = user.ranked_score
        n_total_score = user.total_score
        n_xh = user.count_xh
        n_x = user.count_x
        n_sh = user.count_sh
        n_s = user.count_s
        n_a = user.count_a
        n_play_time = user.play_time
        n_badge_count = user.badge_count
    else:
        gc = statistics.grade_counts
        n_crank = statistics.country_rank
        n_grank = statistics.global_rank
        n_pp = statistics.pp
        n_acc = statistics.hit_accuracy
        n_pc = statistics.play_count
        n_count = statistics.total_hits
        n_ranked_score = statistics.ranked_score
        n_total_score = statistics.total_score
        n_xh = gc.ssh
        n_x = gc.ss
        n_sh = gc.sh
        n_s = gc.s
        n_a = gc.a
        n_play_time = statistics.play_time
        n_badge_count = len(info.badges) if info.badges else 0
    # 获取背景
    bg_path = user_cache_path / str(info.id) / "info.png"
    if bg_path.exists():
        try:
            with open(bg_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

            # 格式化为 CSS 接受的 data URI 格式
            bg = f"data:image/png;base64,{encoded_string}"
        except UnidentifiedImageError:
            bg_path.unlink()
            raise NetworkError("自定义背景图片读取错误，请重新上传！")
    else:
        bg_img = await get_projectimg(get_random_bg())
        encoded_string = base64.b64encode(bg_img.getvalue()).decode("utf-8")
        bg = f"data:image/png;base64,{encoded_string}"
    if day != 0 and user:
        day_delta = date.today() - user.date
        time = day_delta.days
        footer = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        footer += f" | 数据对比于 {time} 天前"
    else:
        footer = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    op, value = info_calc(statistics.pp, n_pp, pp=True)
    pp_change = f"{op}{value:,.2f}" if value != 0 else None
    op, value = info_calc(statistics.global_rank, n_grank, rank=True)
    rank_change = f"{op}{value:,}" if value != 0 else None
    op, value = info_calc(statistics.country_rank, n_crank, rank=True)
    country_rank_change = f"({op}{value:,})" if value != 0 else None
    # acc
    op, value = info_calc(statistics.hit_accuracy, n_acc)
    acc_change = f"({op}{value:.2f}%)" if value != 0 else None
    # 游玩次数
    op, value = info_calc(statistics.play_count, n_pc)
    pc_change = f"({op}{value:,})" if value != 0 else None
    op, value = info_calc(statistics.total_hits, n_count)
    hits_change = f"({op}{value:,})" if value != 0 else None
    op, value = info_calc(statistics.ranked_score, n_ranked_score)
    ranked_score_change = f"({op}{value:,})" if value != 0 and n_ranked_score is not None else None
    op, value = info_calc(statistics.total_score, n_total_score)
    total_score_change = f"({op}{value:,})" if value != 0 and n_total_score is not None else None
    gc = statistics.grade_counts

    def _grade_change(cur, prev):
        if prev is None:
            return None
        op, value = info_calc(cur, prev)
        return f"({op}{value:,})" if value != 0 else None

    xh_change = _grade_change(gc.ssh, n_xh)
    x_change = _grade_change(gc.ss, n_x)
    sh_change = _grade_change(gc.sh, n_sh)
    s_change = _grade_change(gc.s, n_s)
    a_change = _grade_change(gc.a, n_a)
    op, value = info_calc(statistics.play_time, n_play_time)
    play_time_change = f"({op}{value:,}s)" if value != 0 and n_play_time is not None else None
    cur_badge = len(info.badges) if info.badges else 0
    op, value = info_calc(cur_badge, n_badge_count)
    badge_count_change = f"({op}{value:,})" if value != 0 and n_badge_count is not None else None
    badges = [Badge(**i.model_dump()) for i in info.badges] if info.badges else None
    draw_user = DrawUser(
        id=info.id,
        username=info.username,
        country_code=info.country_code,
        mode=mode.upper(),
        badges=badges,
        team=info.team.model_dump() if info.team else None,
        statistics=info.statistics.model_dump() if info.statistics else None,
        footer=footer,
        rank_change=rank_change,
        country_rank_change=country_rank_change,
        pp_change=pp_change,
        acc_change=acc_change,
        pc_change=pc_change,
        hits_change=hits_change,
        ranked_score_change=ranked_score_change,
        total_score_change=total_score_change,
        xh_change=xh_change,
        x_change=x_change,
        sh_change=sh_change,
        s_change=s_change,
        a_change=a_change,
        play_time_change=play_time_change,
        badge_count_change=badge_count_change,
    )
    template_path = str(Path(__file__).parent / "info_templates")
    template_name = "index.html"
    template_env = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(template_path),
        enable_async=True,
    )
    template = template_env.get_template(template_name)
    async with get_new_page(2) as page:
        await page.goto(f"file://{template_path}")
        await page.set_content(
            await template.render_async(user_json=draw_user.model_dump_json(), bg=bg), wait_until="load"
        )
        elem = await page.query_selector("#display")
        assert elem
        return await elem.screenshot(type="jpeg")
