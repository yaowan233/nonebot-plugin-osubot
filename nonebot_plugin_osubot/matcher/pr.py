from nonebot import on_command
from nonebot_plugin_alconna import UniMessage
from nonebot.params import T_State

from ..api import get_user_info
from .utils import split_msg
from ..draw import draw_score
from ..schema import Score
from ..api import osu_api
from ..draw.bp import draw_pfm
from ..utils import NGM

recent = on_command("recent", priority=11, block=True, aliases={'re', 'RE', 'Re', 'rE'})
pr = on_command("pr", priority=11, block=True, aliases={'PR', 'Pr', 'pR'})


@recent.handle(parameterless=[split_msg()])
async def _recent(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    mode = NGM[state["mode"]]
    if "-" in state["para"]:
        ls = state["para"].split("-")
        low, high = ls[0], ls[1]
        data = await osu_api(
            "recent",
            state["user"],
            mode,
            is_name=state["is_name"],
            offset=low,
            limit=high,
        )
        if not data:
            await UniMessage.text(f"未查询到在 {mode} 的游玩记录").send(reply_to=True)
            return
        if isinstance(data, str):
            await UniMessage.text(data).send(reply_to=True)
        if not state["is_name"]:
            info = await get_user_info(
                f"https://osu.ppy.sh/api/v2/users/{state['user']}?key=id"
            )
            if isinstance(info, str):
                return info
            else:
                state["user"] = info["username"]
        score_ls = [Score(**score_json) for score_json in data]
        pic = await draw_pfm("relist", state["user"], score_ls, score_ls, mode)
        await UniMessage.image(raw=pic).send(reply_to=True)
        return
    if state["day"] == 0:
        state["day"] = 1
    data = await draw_score(
        "recent", state["user"], mode, [], state["day"] - 1, is_name=state["is_name"]
    )
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
        return
    await UniMessage.image(raw=data).send(reply_to=True)


@pr.handle(parameterless=[split_msg()])
async def _pr(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    mode = state["mode"]
    if "-" in state["para"]:
        ls = state["para"].split("-")
        low, high = ls[0], ls[1]
        data = await osu_api(
            "pr",
            state["user"],
            NGM[mode],
            is_name=state["is_name"],
            offset=low,
            limit=high,
        )
        if not data:
            await UniMessage.text(f"未查询到在 {NGM[mode]} 的游玩记录").send(reply_to=True)
            return
        if isinstance(data, str):
            await UniMessage.text(data).send(reply_to=True)
            return
        if not state["is_name"]:
            info = await get_user_info(
                f"https://osu.ppy.sh/api/v2/users/{state['user']}?key=id"
            )
            if isinstance(info, str):
                return info
            else:
                state["user"] = info["username"]
        score_ls = [Score(**score_json) for score_json in data]
        pic = await draw_pfm("prlist", state["user"], score_ls, score_ls, NGM[mode])
        await UniMessage.image(raw=pic).send(reply_to=True)
        return
    data = await draw_score(
        "pr", state["user"], NGM[mode], [], is_name=state["is_name"]
    )
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
        return
    await UniMessage.image(raw=data).send(reply_to=True)
