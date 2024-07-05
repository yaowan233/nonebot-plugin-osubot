import datetime

from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from ..database import InfoData, UserData
from ..draw.echarts import draw_history_plot

history = on_command("history", priority=11, block=True)


@history.handle(parameterless=[split_msg()])
async def _info(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    data = InfoData.filter(osu_id=state["user"], osu_mode=state["mode"])
    user = await UserData.filter(osu_id=state["user"]).first()
    if state["day"] > 0:
        data = data.filter(date__gte=datetime.date.today() - datetime.timedelta(days=state["day"]))
    data = await data.order_by("date").all()
    pp_ls = [i.pp for i in data]
    date_ls = [str(i.date) for i in data]
    rank_ls = [i.g_rank for i in data]
    byt = await draw_history_plot(pp_ls, date_ls, rank_ls, f'{user.osu_name} {NGM[state["mode"]]} pp/rank history')
    await UniMessage.image(raw=byt).finish(reply_to=True)
