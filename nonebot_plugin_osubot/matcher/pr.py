from nonebot import on_command
from nonebot.params import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from ..draw import draw_score
from ..draw.bp import draw_pfm
from ..database import UserData
from ..api import get_user_scores
from ..exceptions import NetworkError
from ..draw.score import cal_score_info

recent = on_command("recent", priority=11, block=True, aliases={"re", "RE", "Re", "rE"})
pr = on_command("pr", priority=11, block=True, aliases={"PR", "Pr", "pR"})


@recent.handle(parameterless=[split_msg()])
async def _recent(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    mode = NGM[state["mode"]]
    player = await UserData.get_or_none(user_id=event.get_user_id())
    if state["range"]:
        ls = state["range"].split("-")
        low, high = ls[0], ls[1]
        try:
            scores = await get_user_scores(
                state["user"],
                mode,
                "recent",
                state["source"],
                not player.lazer_mode,
                True,
                int(low) - 1,
                high if state["source"] == "ppysb" else int(high) - int(low) + 1,
            )
        except NetworkError as e:
            lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
            mods = f" mod:{state['mods']}" if state["mods"] else ""
            await UniMessage.text(
                f"在查找用户：{state['username']} {NGM[state['mode']]}模式"
                f" {lazer_mode}{mods} 最近{state['range']}成绩时 {str(e)}"
            ).finish(reply_to=True)
        if not player.lazer_mode:
            scores = [i for i in scores if any(mod.acronym == "CL" for mod in i.mods)]
        for score in scores:
            cal_score_info(player.lazer_mode, score)
        pic = await draw_pfm("relist", state["user"], scores, scores, mode, state["source"], is_lazer=player.lazer_mode)
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
async def _pr(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    mode = NGM[state["mode"]]
    player = await UserData.get_or_none(user_id=event.get_user_id())
    if state["range"]:
        ls = state["range"].split("-")
        low, high = ls[0], ls[1]
        try:
            scores = await get_user_scores(
                state["user"],
                mode,
                "recent",
                state["source"],
                not player.lazer_mode,
                False,
                int(low) - 1,
                high if state["source"] == "ppysb" else int(high) - int(low) + 1,
            )
        except NetworkError as e:
            lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
            mods = f" mod:{state['mods']}" if state["mods"] else ""
            await UniMessage.text(
                f"在查找用户：{state['username']} {NGM[state['mode']]}模式"
                f" {lazer_mode}{mods} 最近{state['range']}成绩时 {str(e)}"
            ).finish(reply_to=True)
        if not player.lazer_mode:
            scores = [i for i in scores if any(mod.acronym == "CL" for mod in i.mods)]
        for score_info in scores:
            cal_score_info(player.lazer_mode, score_info)
        pic = await draw_pfm(
            "prlist", state["user"], scores, scores, mode, source=state["source"], is_lazer=player.lazer_mode
        )
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
