from arclet.alconna import Alconna, Args, CommandMeta
from nonebot import on_command
from nonebot.internal.adapter import Message
from nonebot.params import CommandArg
from nonebot_plugin_alconna import on_alconna, UniMessage, Match
from ..info import get_bg

getbg = on_command("getbg", priority=11, block=True)


@getbg.handle()
async def _get_bg(
        bg: Message = CommandArg()
):
    bg = bg.extract_plain_text().strip()
    if not bg:
        await UniMessage.text("请输入需要提取BG的地图ID").send(reply_to=True)
        return
    byt = await get_bg(bg)
    if isinstance(byt, str):
        await UniMessage.text(byt).send(reply_to=True)
        return
    await UniMessage.image(raw=byt).send(reply_to=True)
