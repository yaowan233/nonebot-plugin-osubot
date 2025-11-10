from pathlib import Path

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

osu_help = on_command("osuhelp", aliases={"OSUBot", "osubot"}, priority=11, block=True)

with open(Path(__file__).parent.parent / "osufile" / "help.png", "rb") as f:
    img1 = f.read()
with open(Path(__file__).parent.parent / "osufile" / "detail.png", "rb") as f:
    img2 = f.read()


@osu_help.handle()
async def _help(arg: Message = CommandArg()):
    arg = arg.extract_plain_text().strip()
    if arg == "detail":
        await UniMessage.image(raw=img2).finish(reply_to=True)
    await UniMessage.image(raw=img1).finish(reply_to=True)
