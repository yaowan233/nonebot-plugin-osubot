from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from ..draw import draw_info
from .utils import split_msg
from ..exceptions import NetworkError

info = on_command("info", priority=11, block=True, aliases={"Info", "INFO"})


@info.handle(parameterless=[split_msg()])
async def _info(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    try:
        data = await draw_info(state["user"], NGM[state["mode"]], state["day"], state["is_name"])
    except NetworkError as e:
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式 {state['day']}日内 成绩时{str(e)}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)
