from nonebot import on_command
from nonebot_plugin_alconna import UniMessage
from nonebot.typing import T_State
from .utils import split_msg
from ..draw import get_score_data
from ..utils import NGM


score = on_command("score", priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    data = await get_score_data(
        state["user"],
        NGM[state["mode"]],
        mapid=state["para"],
        mods=state["mods"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
        return
    await UniMessage.image(raw=data).send(reply_to=True)
