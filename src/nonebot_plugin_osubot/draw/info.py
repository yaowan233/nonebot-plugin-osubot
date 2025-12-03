import base64
import jinja2
from pathlib import Path
from typing import Union
from datetime import date, datetime, timedelta

from PIL import UnidentifiedImageError
from nonebot_plugin_htmlrender import get_new_page

from .utils import info_calc
from ..utils import FGM, GMN
from ..file import user_cache_path
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
    user = await InfoData.filter(osu_id=info.id, osu_mode=FGM[mode]).order_by("-date").first()
    if user:
        today_date = date.today()
        query_date = today_date - timedelta(days=day)
        if (
            user := await InfoData.filter(osu_id=info.id, osu_mode=FGM[mode], date__gte=query_date)
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
        bg = get_random_bg()
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
    # 总分
    # 总命中
    op, value = info_calc(statistics.total_hits, n_count)
    hits_change = f"({op}{value:,})" if value != 0 else None
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
            await template.render_async(user_json=draw_user.model_dump_json(), bg=bg), wait_until="networkidle"
        )
        elem = await page.query_selector("#display")
        assert elem
        return await elem.screenshot(type="jpeg")
