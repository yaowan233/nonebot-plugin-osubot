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
from nonebot.internal.adapter import Message
from nonebot.params import CommandArg
from nonebot_plugin_guild_patch import GuildMessageEvent

from ..info import get_bg

getbg = on_command("getbg", priority=11, block=True)


@getbg.handle()
async def _get_bg(
    event: Union[v11MessageEvent, GuildMessageEvent], args: Message = CommandArg()
):
    bg_id = args.extract_plain_text().strip()
    if not bg_id:
        msg = "请输入需要提取BG的地图ID"
    else:
        byt = await get_bg(bg_id)
        if isinstance(byt, str):
            await getbg.finish(v11MessageSegment.reply(event.message_id) + byt)
        msg = v11MessageSegment.image(byt)
    await getbg.finish(v11MessageSegment.reply(event.message_id) + msg)


@getbg.handle()
async def _get_bg(event: RedMessageEvent, args: Message = CommandArg()):
    bg_id = args.extract_plain_text().strip()
    if not bg_id:
        msg = "请输入需要提取BG的地图ID"
    else:
        byt = await get_bg(bg_id)
        if isinstance(byt, str):
            await getbg.finish(
                RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
                + byt
            )
        msg = RedMessageSegment.image(byt)
    await getbg.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + msg
    )
