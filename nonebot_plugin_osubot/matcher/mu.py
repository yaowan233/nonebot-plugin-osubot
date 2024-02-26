from arclet.alconna import Alconna, CommandMeta
from nonebot.typing import T_State
from nonebot_plugin_alconna import on_alconna, UniMessage
from .utils import split_msg


mu = on_alconna(
    Alconna(
        "mu",
        meta=CommandMeta(example="/mu"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)


@mu.handle(parameterless=[split_msg()])
async def _mu(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
    await UniMessage.text(f"https://osu.ppy.sh/u/{state['user']}").send(reply_to=True)
