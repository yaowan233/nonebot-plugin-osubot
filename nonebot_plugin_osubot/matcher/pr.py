from nonebot import on_command
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage
from nonebot.params import T_State

from ..database import UserData
from ..api import get_user_info
from .utils import split_msg
from ..draw import draw_score
from ..draw.score import cal_legacy_acc, cal_legacy_rank
from ..schema import NewScore
from ..api import osu_api
from ..draw.bp import draw_pfm
from ..utils import NGM

recent = on_command("recent", priority=11, block=True, aliases={"re", "RE", "Re", "rE"})
pr = on_command("pr", priority=11, block=True, aliases={"PR", "Pr", "pR"})


@recent.handle(parameterless=[split_msg()])
async def _recent(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    mode = NGM[state["mode"]]
    if "-" in state["para"]:
        ls = state["para"].split("-")
        low, high = ls[0], ls[1]
        data = await osu_api(
            "recent",
            state["user"],
            mode,
            is_name=state["is_name"],
            offset=int(low) - 1,
            limit=high,
        )
        if not data:
            await UniMessage.text(f"未查询到在 {mode} 的游玩记录").finish(reply_to=True)
        if isinstance(data, str):
            await UniMessage.text(data).finish(reply_to=True)
        if not state["is_name"]:
            info = await get_user_info(f"https://osu.ppy.sh/api/v2/users/{state['user']}?key=id")
            if isinstance(info, str):
                await UniMessage.text(info).finish(reply_to=True)
            else:
                state["user"] = info["username"]
        score_ls = [NewScore(**score_json) for score_json in data]
        player = await UserData.get_or_none(user_id=int(event.get_user_id()))
        if not player.lazer_mode:
            score_ls = [i for i in score_ls if {"acronym": "CL"} in i.mods]
        for score_info in score_ls:
            if not player.lazer_mode:
                score_info.mods.remove({"acronym": "CL"}) if {"acronym": "CL"} in score_info.mods else None
            if score_info.ruleset_id == 3 and not player.lazer_mode:
                score_info.accuracy = cal_legacy_acc(score_info.statistics)
            if not player.lazer_mode:
                is_hidden = any(i in score_info.mods for i in ({"acronym": "HD"}, {"acronym": "FL"}, {"acronym": "FI"}))
                score_info.rank = cal_legacy_rank(score_info, is_hidden)
        pic = await draw_pfm("relist", state["user"], score_ls, score_ls, mode)
        await UniMessage.image(raw=pic).finish(reply_to=True)
    if state["day"] == 0:
        state["day"] = 1
    data = await draw_score(
        "recent",
        state["user"],
        int(event.get_user_id()),
        mode,
        [],
        state["day"] - 1,
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await UniMessage.text(data).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)


@pr.handle(parameterless=[split_msg()])
async def _pr(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    mode = state["mode"]
    if "-" in state["para"]:
        ls = state["para"].split("-")
        low, high = ls[0], ls[1]
        data = await osu_api(
            "pr",
            state["user"],
            NGM[mode],
            is_name=state["is_name"],
            offset=int(low) - 1,
            limit=high,
        )
        if not data:
            await UniMessage.text(f"未查询到在 {NGM[mode]} 的游玩记录").finish(reply_to=True)
        if isinstance(data, str):
            await UniMessage.text(data).finish(reply_to=True)
        if not state["is_name"]:
            info = await get_user_info(f"https://osu.ppy.sh/api/v2/users/{state['user']}?key=id")
            if isinstance(info, str):
                return info
            else:
                state["user"] = info["username"]
        score_ls = [NewScore(**score_json) for score_json in data]
        player = await UserData.get_or_none(user_id=int(event.get_user_id()))
        if not player.lazer_mode:
            score_ls = [i for i in score_ls if {"acronym": "CL"} in i.mods]
        for score_info in score_ls:
            if not player.lazer_mode:
                score_info.mods.remove({"acronym": "CL"}) if {"acronym": "CL"} in score_info.mods else None
            if score_info.ruleset_id == 3 and not player.lazer_mode:
                score_info.accuracy = cal_legacy_acc(score_info.statistics)
            if not player.lazer_mode:
                is_hidden = any(i in score_info.mods for i in ({"acronym": "HD"}, {"acronym": "FL"}, {"acronym": "FI"}))
                score_info.rank = cal_legacy_rank(score_info, is_hidden)
        pic = await draw_pfm("prlist", state["user"], score_ls, score_ls, NGM[mode])
        await UniMessage.image(raw=pic).finish(reply_to=True)
    if state["day"] == 0:
        state["day"] = 1
    data = await draw_score(
        "pr",
        state["user"],
        int(event.get_user_id()),
        NGM[mode],
        [],
        state["day"] - 1,
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await UniMessage.text(data).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)
