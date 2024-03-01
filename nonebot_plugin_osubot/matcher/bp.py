from nonebot import on_command
from nonebot_plugin_alconna import UniMessage
from nonebot.typing import T_State
from .utils import split_msg
from ..draw import draw_score, draw_bp
from ..utils import NGM

bp = on_command("bp", priority=11, block=True)

pfm = on_command("pfm", priority=11, block=True)
tbp = on_command("tbp", priority=11, block=True, aliases={'todaybp'})


@bp.handle(parameterless=[split_msg()])
async def _bp(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    if "-" in state["para"]:
        await _pfm(state)
        return
    best = state["para"]
    if not best:
        best = "1"
    if not best.isdigit():
        await UniMessage.text("只能接受纯数字的bp参数").send(reply_to=True)
        return
    best = int(best)
    if best <= 0 or best > 100:
        await UniMessage.text("只允许查询bp 1-100 的成绩").send(reply_to=True)
        return
    data = await draw_score(
        "bp",
        state["user"],
        NGM[state["mode"]],
        best=best,
        mods=state["mods"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
        return
    await UniMessage.image(raw=data).send(reply_to=True)


@pfm.handle(parameterless=[split_msg()])
async def _pfm(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    ls = state["para"].split("-")
    low, high = ls[0], ls[1]
    if not low.isdigit() or not high.isdigit():
        await UniMessage.text('参数应为 "数字-数字"的形式!').send(reply_to=True)
        return
    low, high = int(low), int(high)
    if not 0 < low < high <= 100:
        await UniMessage.text("仅支持查询bp1-100").send(reply_to=True)
        return
    data = await draw_bp(
        "bp",
        state["user"],
        NGM[state["mode"]],
        state["mods"],
        low,
        high,
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
        return
    await UniMessage.image(raw=data).send(reply_to=True)


@tbp.handle(parameterless=[split_msg()])
async def _tbp(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    data = await draw_bp(
        "tbp",
        state["user"],
        NGM[state["mode"]],
        [],
        day=state["day"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
        return
    await UniMessage.image(raw=data).send(reply_to=True)
