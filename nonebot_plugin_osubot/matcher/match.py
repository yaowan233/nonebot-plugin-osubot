from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

from ..draw.match_history import draw_match_history

match = on_command("match", priority=11, block=True)


@match.handle()
async def _help(arg: Message = CommandArg()):
    arg = arg.extract_plain_text().strip()
    img = await draw_match_history(arg)
    await UniMessage.image(raw=img).finish(reply_to=True)
