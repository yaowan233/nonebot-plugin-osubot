from typing import Union
from nonebot_plugin_guild_patch import GuildMessageEvent
from nonebot import on_command
from nonebot.adapters.red import (
    MessageSegment as RedMessageSegment,
    MessageEvent as RedMessageEvent,
)
from nonebot.adapters.onebot.v11 import (
    MessageEvent as v11MessageEvent,
    MessageSegment as v11MessageSegment,
)
from nonebot.typing import T_State
from .utils import split_msg
from ..draw import get_score_data
from ..utils import NGM


score = on_command("score", priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await score.finish(v11MessageSegment.reply(event.message_id) + state["error"])
    data = await get_score_data(
        state["user"],
        NGM[state["mode"]],
        mapid=state["para"],
        mods=state["mods"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await score.finish(v11MessageSegment.reply(event.message_id) + data)
    await score.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(data)
    )


@score.handle(parameterless=[split_msg()])
async def _score(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await score.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
    data = await get_score_data(
        state["user"],
        NGM[state["mode"]],
        mapid=state["para"],
        mods=state["mods"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await score.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + data
        )
    await score.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(data)
    )
