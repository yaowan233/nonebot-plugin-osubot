from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

from ..file import download_map, upload_file_stream_batch

osudl = on_command("osudl", priority=11, block=True)


@osudl.handle()
async def _osudl(bot: Bot, event: GroupMessageEvent, setid: Message = CommandArg()):
    setid = setid.extract_plain_text().strip()
    if not setid or not setid.isdigit():
        await UniMessage.text("请输入正确的地图ID").send(reply_to=True)
    osz_path = await download_map(int(setid))
    server_osz_path = await upload_file_stream_batch(bot, osz_path)
    try:
        await bot.call_api("upload_group_file", group_id=event.group_id, file=server_osz_path, name=osz_path.name)
    except Exception:
        await UniMessage.text("上传文件失败，可能是群空间满或没有权限导致的").send(reply_to=True)
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...
