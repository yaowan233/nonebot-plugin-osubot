from arclet.alconna import Alconna, Args, CommandMeta
from nonebot_plugin_alconna import on_alconna, UniMessage, Match
from ..info import get_bg

getbg = on_alconna(
    Alconna(
        "getbg",
        Args["bg?", str],
        meta=CommandMeta(example="/getbg 4374648"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)


@getbg.handle()
async def _get_bg(
    bg: Match[str],
):
    bg = bg.result.strip() if bg.available else ""
    if not bg:
        await UniMessage.text("请输入需要提取BG的地图ID").send(reply_to=True)
        return
    byt = await get_bg(bg)
    if isinstance(byt, str):
        await UniMessage.text(byt).send(reply_to=True)
        return
    await UniMessage.image(raw=byt).send(reply_to=True)
