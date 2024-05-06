from nonebot import on_command
from nonebot.internal.adapter import Message
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage
from ..info import get_bg

getbg = on_command("getbg", priority=11, block=True)


@getbg.handle()
async def _get_bg(bg: Message = CommandArg()):
    bg = bg.extract_plain_text().strip()
    if not bg:
        await UniMessage.text("请输入需要提取BG的地图ID").finish(reply_to=True)
    byt = await get_bg(bg)
    if isinstance(byt, str):
        await UniMessage.text(byt).finish(reply_to=True)
    await UniMessage.image(raw=byt).finish(reply_to=True)
