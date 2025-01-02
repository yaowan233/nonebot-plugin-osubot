from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from ..exceptions import NetworkError
from ..draw import draw_bp, draw_score

bp = on_command("bp", priority=11, block=True)
pfm = on_command("pfm", priority=11, block=True, aliases={"bplist"})
tbp = on_command("tbp", priority=11, block=True, aliases={"todaybp"})


@bp.handle(parameterless=[split_msg()])
async def _bp(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if state["range"]:
        await _pfm(state)
        return
    best = state["target"]
    if not best:
        best = "1"
    if not best.isdigit():
        await UniMessage.text("只能接受纯数字的bp参数").finish(reply_to=True)
    best = int(best)
    if best <= 0 or best > 100:
        await UniMessage.text("只允许查询bp 1-100 的成绩").finish(reply_to=True)
    try:
        data = await draw_score(
            "bp",
            state["user"],
            state["is_lazer"],
            NGM[state["mode"]],
            state["mods"],
            state["query"],
            state["source"],
            best=best,
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式" f" bp{best} {lazer_mode}{mods}时 {str(e)}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)


@pfm.handle(parameterless=[split_msg()])
async def _pfm(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if not state["range"]:
        state["range"] = "1-100"
    ls = state["range"].split("-")
    low, high = int(ls[0]), int(ls[1])
    if not 0 < low < high <= 100:
        await UniMessage.text("仅支持查询bp1-100").finish(reply_to=True)
    try:
        data = await draw_bp(
            "bp",
            state["user"],
            state["is_lazer"],
            NGM[state["mode"]],
            state["mods"],
            low,
            high,
            state["day"],
            state["query"],
            state["source"],
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式"
            f" bp{state['range']} {lazer_mode}{mods}时 {str(e)}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)


@tbp.handle(parameterless=[split_msg()])
async def _tbp(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if not state["range"]:
        state["range"] = "1-100"
    ls = state["range"].split("-")
    low, high = int(ls[0]), int(ls[1])
    if not 0 < low < high <= 100:
        await UniMessage.text("仅支持查询bp1-100").finish(reply_to=True)
    try:
        data = await draw_bp(
            "tbp",
            state["user"],
            state["is_lazer"],
            NGM[state["mode"]],
            state["mods"],
            low,
            high,
            state["day"],
            state["query"],
            state["source"],
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式"
            f"{lazer_mode}{mods} {state['day']}日内最佳成绩时 {str(e)}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)
