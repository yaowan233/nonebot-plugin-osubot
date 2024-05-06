from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage
from .utils import split_msg


mu = on_command("mu", priority=11, block=True)


@mu.handle(parameterless=[split_msg()])
async def _mu(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    await UniMessage.text(f"https://osu.ppy.sh/u/{state['user']}").finish(reply_to=True)
