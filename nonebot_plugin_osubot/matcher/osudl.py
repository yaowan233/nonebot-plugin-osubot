import urllib
from nonebot import on_command
from nonebot.adapters.red import (
    MessageSegment as RedMessageSegment,
    GroupMessageEvent as RedGroupMessageEvent,
)
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent as v11GroupMessageEvent,
    MessageSegment as v11MessageSegment,
    ActionFailed,
    Bot as v11Bot,
)
from nonebot.internal.adapter import Message
from nonebot.params import CommandArg

from ..file import download_map

osudl = on_command("osudl", priority=11, block=True)


@osudl.handle()
async def _osudl(
    bot: v11Bot,
    event: v11GroupMessageEvent,
    msg: Message = CommandArg(),
):
    setid = msg.extract_plain_text().strip()
    if not setid or not setid.isdigit():
        await osudl.finish(v11MessageSegment.reply(event.message_id) + "请输入正确的地图ID")
    osz_path = await download_map(int(setid))
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await bot.upload_group_file(
            group_id=event.group_id, file=str(file_path), name=name
        )
    except ActionFailed:
        await osudl.finish(
            v11MessageSegment.reply(event.message_id) + "上传文件失败，可能是群空间满或没有权限导致的"
        )
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...


@osudl.handle()
async def _osudl(
    event: RedGroupMessageEvent,
    msg: Message = CommandArg(),
):
    setid = msg.extract_plain_text().strip()
    if not setid or not setid.isdigit():
        await osudl.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请输入正确的地图ID"
        )
    osz_path = await download_map(int(setid))
    file_path = osz_path.absolute()
    try:
        await osudl.finish(RedMessageSegment.file(file_path))
    except Exception as e:
        print(e)
        await osudl.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "上传文件失败，可能是群空间满或没有权限导致的"
        )
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...
