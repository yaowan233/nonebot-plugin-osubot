import asyncio
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

from ..info import bind_user_info
from ..database import UserData


bind = on_command("bind", priority=11, block=True)
lock = asyncio.Lock()


@bind.handle()
async def _bind(
    event: Union[v11MessageEvent, GuildMessageEvent], args: Message = CommandArg()
):
    name = args.extract_plain_text()
    if not name:
        await bind.finish(v11MessageSegment.reply(event.message_id) + "请输入您的 osuid")
    async with lock:
        if _ := await UserData.get_or_none(user_id=event.get_user_id()):
            await bind.finish(
                v11MessageSegment.reply(event.message_id) + "您已绑定，如需要解绑请输入/unbind"
            )
        msg = await bind_user_info("bind", name, event.get_user_id(), True)
    await bind.finish(v11MessageSegment.reply(event.message_id) + msg)


@bind.handle()
async def _bind(event: RedMessageEvent, args: Message = CommandArg()):
    name = args.extract_plain_text()
    if not name:
        await bind.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请输入您的 osuid"
        )
    async with lock:
        if _ := await UserData.get_or_none(user_id=event.get_user_id()):
            await bind.finish(
                RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
                + "您已绑定，如需要解绑请输入/unbind"
            )
        msg = await bind_user_info("bind", name, event.get_user_id(), True)
    await bind.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + msg
    )


unbind = on_command("unbind", priority=11, block=True)


@unbind.handle()
async def _unbind(event: Union[v11MessageEvent, GuildMessageEvent]):
    if _ := await UserData.get_or_none(user_id=event.get_user_id()):
        await UserData.filter(user_id=event.get_user_id()).delete()
        await unbind.finish(v11MessageSegment.reply(event.message_id) + "解绑成功！")
    else:
        await unbind.finish(v11MessageSegment.reply(event.message_id) + "尚未绑定，无需解绑")


@unbind.handle()
async def _unbind(event: RedMessageEvent):
    if _ := await UserData.get_or_none(user_id=event.get_user_id()):
        await UserData.filter(user_id=event.get_user_id()).delete()
        await unbind.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "解绑成功！"
        )
    else:
        await unbind.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "尚未绑定，无需解绑"
        )
