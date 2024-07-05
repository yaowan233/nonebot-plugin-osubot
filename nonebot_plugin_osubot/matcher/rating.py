from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

from ..draw.rating import draw_rating

rating = on_command("rating", priority=11, block=True)


@rating.handle()
async def _(arg: Message = CommandArg()):
    arg = arg.extract_plain_text().strip()
    img = await draw_rating(arg)
    await UniMessage.image(raw=img).finish(reply_to=True)
