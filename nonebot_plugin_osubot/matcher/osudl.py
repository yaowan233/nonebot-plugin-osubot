from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

from ..file import download_map

osudl = on_command("osudl", priority=11, block=True)


@osudl.handle()
async def _osudl(setid: Message = CommandArg()):
    setid = setid.extract_plain_text().strip()
    if not setid or not setid.isdigit():
        await UniMessage.text("请输入正确的地图ID").send(reply_to=True)
    osz_path = await download_map(int(setid))
    file_path = osz_path.absolute()
    try:
        await UniMessage.file(path=file_path).send()
    except Exception:
        await UniMessage.text("上传文件失败，可能是群空间满或没有权限导致的").send(reply_to=True)
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...
