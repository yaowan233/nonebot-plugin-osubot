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


mu = on_command("mu", aliases={"Mu", "MU"}, block=True, priority=11)


@mu.handle(parameterless=[split_msg()])
async def _mu(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await mu.finish(v11MessageSegment.reply(event.message_id) + state["error"])
    await mu.finish(
        v11MessageSegment.reply(event.message_id)
        + f"https://osu.ppy.sh/u/{state['user']}"
    )


@mu.handle(parameterless=[split_msg()])
async def _mu(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await mu.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
    await mu.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + f"https://osu.ppy.sh/u/{state['user']}"
    )
