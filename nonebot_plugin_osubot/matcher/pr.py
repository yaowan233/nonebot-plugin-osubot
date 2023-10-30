from typing import Union

from nonebot import on_command
from nonebot.adapters.red import (
    MessageSegment as RedMessageSegment,
    MessageEvent as RedMessageEvent,
)
from nonebot.adapters.onebot.v11 import (
    MessageEvent as v11MessageEvent,
    MessageSegment as v11MessageSegment,
)
from nonebot.params import T_State
from nonebot_plugin_guild_patch import GuildMessageEvent

from ..api import get_user_info
from .utils import split_msg
from ..draw import draw_score
from ..schema import Score
from ..api import osu_api
from ..draw.bp import draw_pfm
from ..utils import NGM

recent = on_command("recent", aliases={"re", "RE", "Re"}, priority=11, block=True)
pr = on_command("pr", priority=11, block=True, aliases={"PR", "Pr"})


@recent.handle(parameterless=[split_msg()])
async def _recent(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await recent.finish(v11MessageSegment.reply(event.message_id) + state["error"])
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
            await recent.finish(
                v11MessageSegment.reply(event.message_id) + f"未查询到在 {mode} 的游玩记录"
            )
        if isinstance(data, str):
            await recent.finish(v11MessageSegment.reply(event.message_id) + data)
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
        await recent.finish(
            v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(pic)
        )
    if state["day"] == 0:
        state["day"] = 1
    data = await draw_score(
        "recent", state["user"], mode, [], state["day"] - 1, is_name=state["is_name"]
    )
    if isinstance(data, str):
        await recent.finish(v11MessageSegment.reply(event.message_id) + data)
    await recent.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(data)
    )


@pr.handle(parameterless=[split_msg()])
async def _pr(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await pr.finish(v11MessageSegment.reply(event.message_id) + state["error"])
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
            await pr.finish(
                v11MessageSegment.reply(event.message_id) + f"未查询到在 {NGM[mode]} 的游玩记录"
            )
        if isinstance(data, str):
            await pr.finish(v11MessageSegment.reply(event.message_id) + data)
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
        await pr.finish(
            v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(pic)
        )
    data = await draw_score(
        "pr", state["user"], NGM[mode], [], is_name=state["is_name"]
    )
    if isinstance(data, str):
        await pr.finish(v11MessageSegment.reply(event.message_id) + data)
    await pr.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(data)
    )


@recent.handle(parameterless=[split_msg()])
async def _recent(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await recent.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
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
            await recent.finish(
                RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
                + f"未查询到在 {mode} 的游玩记录"
            )
        if isinstance(data, str):
            await recent.finish(
                RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
                + data
            )
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
        await recent.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + RedMessageSegment.image(pic)
        )
    if state["day"] == 0:
        state["day"] = 1
    data = await draw_score(
        "recent", state["user"], mode, [], state["day"] - 1, is_name=state["is_name"]
    )
    if isinstance(data, str):
        await recent.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + data
        )
    await recent.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(data)
    )


@pr.handle(parameterless=[split_msg()])
async def _pr(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await pr.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
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
            await pr.finish(
                RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
                + f"未查询到在 {NGM[mode]} 的游玩记录"
            )
        if isinstance(data, str):
            await pr.finish(
                RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
                + data
            )
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
        await pr.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + RedMessageSegment.image(pic)
        )
    data = await draw_score(
        "pr", state["user"], NGM[mode], [], is_name=state["is_name"]
    )
    if isinstance(data, str):
        await pr.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + data
        )
    await pr.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(data)
    )
