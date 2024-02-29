from pathlib import Path
from arclet.alconna import Alconna, Args, CommandMeta
from nonebot_plugin_alconna import on_alconna, UniMessage, Match

osu_help = on_alconna(
    Alconna(
        "osuhelp",
        Args["arg?", str],
        meta=CommandMeta(example="/osuhelp"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)

with open(Path(__file__).parent.parent / "osufile" / "help.png", "rb") as f:
    img1 = f.read()
with open(Path(__file__).parent.parent / "osufile" / "detail.png", "rb") as f:
    img2 = f.read()


@osu_help.handle()
async def _help(arg: Match[str]):
    arg = arg.result.strip() if arg.available else ""
    if arg == "detail":
        await UniMessage.image(raw=img2).send(reply_to=True)
    await UniMessage.image(raw=img1).send(reply_to=True)
