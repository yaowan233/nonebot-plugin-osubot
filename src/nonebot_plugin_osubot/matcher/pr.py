from nonebot import on_command
from nonebot.params import T_State
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from ..draw import draw_score
from ..draw.bp import draw_pfm
from ..api import get_user_scores
from ..exceptions import NetworkError
from ..draw.score import cal_score_info

recent = on_command("recent", priority=11, block=True, aliases={"re", "RE", "Re", "rE"})
pr = on_command("pr", priority=11, block=True, aliases={"PR", "Pr", "pR"})
recent_list = on_command("rl", priority=11, block=True, aliases={"relist", "recentlist"})
pass_list = on_command("pl", priority=11, block=True, aliases={"prlist", "passlist"})


async def _draw_recent_list(state: T_State, include_fails: bool, project: str):
    mode = NGM[state["mode"]]
    low, high = map(int, state["range"].split("-"))
    if not 0 < low <= high <= 200:
        await UniMessage.text("仅支持查询最近1-200条成绩").finish(reply_to=True)
    try:
        scores = await get_user_scores(
            state["user"],
            mode,
            "recent",
            state["source"],
            not state["is_lazer"],
            include_fails,
            low - 1,
            high if state["source"] == "ppysb" else high - low + 1,
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {mode}模式"
            f" {lazer_mode}{mods} 最近{state['range']}成绩时 {str(e)}"
        ).finish(reply_to=True)
    for score in scores:
        cal_score_info(state["is_lazer"], score, state["source"])
    return await draw_pfm(project, state["user"], scores, scores, mode, source=state["source"])


@recent_list.handle(parameterless=[split_msg()])
async def _recent_list(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if not state["range"]:
        state["range"] = "1-30"
    pic = await _draw_recent_list(state, include_fails=True, project="relist")
    await UniMessage.image(raw=pic).finish(reply_to=True)


@pass_list.handle(parameterless=[split_msg()])
async def _pass_list(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if not state["range"]:
        state["range"] = "1-30"
    pic = await _draw_recent_list(state, include_fails=False, project="prlist")
    await UniMessage.image(raw=pic).finish(reply_to=True)


@recent.handle(parameterless=[split_msg()])
async def _recent(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    mode = NGM[state["mode"]]
    if state["range"]:
        pic = await _draw_recent_list(state, include_fails=True, project="relist")
        await UniMessage.image(raw=pic).finish(reply_to=True)
    if state["day"] == 0:
        state["day"] = 1
    try:
        data = await draw_score(
            "recent",
            state["user"],
            state["is_lazer"],
            mode,
            [],
            [],
            state["source"],
            state["day"],
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式"
            f" {lazer_mode}{mods} 最近第{state['day']}个成绩时 {str(e)}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)


@pr.handle(parameterless=[split_msg()])
async def _pr(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    mode = NGM[state["mode"]]
    if state["range"]:
        pic = await _draw_recent_list(state, include_fails=False, project="prlist")
        await UniMessage.image(raw=pic).finish(reply_to=True)
    if state["day"] == 0:
        state["day"] = 1
    try:
        data = await draw_score(
            "pr",
            state["user"],
            state["is_lazer"],
            mode,
            [],
            [],
            state["source"],
            state["day"],
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式"
            f" {lazer_mode}{mods} 最近第{state['day']}个成绩时 {str(e)}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)
