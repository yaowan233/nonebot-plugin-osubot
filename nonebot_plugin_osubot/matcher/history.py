from io import BytesIO

import matplotlib.pyplot as plt
import datetime
from nonebot import on_command
from nonebot_plugin_alconna import UniMessage
from nonebot.typing import T_State
from .utils import split_msg
from ..utils import NGM
from ..database import InfoData, UserData

history = on_command("history", priority=11, block=True)


@history.handle(parameterless=[split_msg()])
async def _info(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    data = InfoData.filter(osu_id=state["user"], osu_mode=state["mode"])
    user = await UserData.filter(osu_id=state["user"]).first()
    if state["day"] > 0:
        data = data.filter(
            date__gte=datetime.date.today() - datetime.timedelta(days=state["day"])
        )
    data = await data.order_by("date").all()
    pp_ls = [i.pp for i in data]
    date_ls = [i.date for i in data]
    rank_ls = [i.g_rank for i in data]
    byt = draw_plot(
        pp_ls, date_ls, rank_ls, f'{user.osu_name} {NGM[state["mode"]]} pp/rank history'
    )
    await UniMessage.image(raw=byt).finish(reply_to=True)


def draw_plot(pp_ls, date_ls, rank_ls, title):
    fig = plt.figure(num="draw_double_line", figsize=(20, 6))
    ax1 = fig.add_subplot(111)
    ax1.plot(date_ls, pp_ls, "black", label="pp")
    ax1.legend(loc="upper left")
    ax2 = ax1.twinx()
    ax2.plot(date_ls, rank_ls, "r", label="rank")
    ax2.legend(loc="upper right")
    ax2.invert_yaxis()
    plt.grid()
    plt.xlabel("date", fontsize=15)
    plt.title(title)
    byt = BytesIO()
    plt.savefig(byt, format="png")
    plt.close()
    return byt
