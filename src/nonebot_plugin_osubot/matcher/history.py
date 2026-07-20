import datetime

from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..utils import NGM
from .utils import split_msg
from ..database import InfoData, UserData
from ..draw.echarts import draw_history_plot
from ..history_data import merge_osutrack_history

history = on_command("history", aliases={"hs"}, priority=11, block=True)


@history.handle(parameterless=[split_msg()])
async def _info(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    query = select(InfoData).where(InfoData.osu_id == state["user"], InfoData.osu_mode == int(state["mode"]))
    if state["day"] > 0:
        query = query.where(InfoData.date >= datetime.date.today() - datetime.timedelta(days=state["day"]))
    query = query.order_by(InfoData.date)
    async with get_session() as session:
        user = await session.scalar(select(UserData).where(UserData.osu_id == state["user"]))
        data = (await session.scalars(query)).all()
    display_name = user.osu_name if user else state["username"] or str(state["user"])
    pp_ls = [i.pp for i in data]
    date_ls = [str(i.date) for i in data]
    rank_ls = [i.g_rank for i in data]
    # 使用列表推导式筛选出 rank_ls 不为 None 的索引
    filtered_indices = [index for index, rank in enumerate(rank_ls) if rank is not None and rank != 0]

    # 根据筛选出的索引生成新的列表
    pp_ls = [pp_ls[i] for i in filtered_indices]
    date_ls = [date_ls[i] for i in filtered_indices]
    rank_ls = [rank_ls[i] for i in filtered_indices]
    has_local_points = bool(pp_ls)
    points, used_osutrack = await merge_osutrack_history(
        state["user"],
        int(state["mode"]),
        zip(pp_ls, date_ls, rank_ls),
        state["day"],
    )
    if not points:
        await UniMessage.text(f"没有找到 {display_name} 的历史数据").finish(reply_to=True)
    pp_ls, date_ls, rank_ls = map(list, zip(*points))
    source_label = "本地记录"
    if used_osutrack:
        source_label = "本地记录 + osu!track" if has_local_points else "osu!track"
    byt = await draw_history_plot(
        pp_ls,
        date_ls,
        rank_ls,
        f"{display_name} {NGM[state['mode']]} pp/rank history",
        username=display_name,
        mode=NGM[state["mode"]],
        user_id=state["user"],
        source_label=source_label,
    )
    await UniMessage.image(raw=byt).finish(reply_to=True)
