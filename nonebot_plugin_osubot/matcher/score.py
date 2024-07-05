from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from ..draw import get_score_data

score = on_command("score", priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if not state["para"].isdigit():
        await UniMessage.text("请输入正确的谱面ID").finish(reply_to=True)
    data = await get_score_data(
        state["user"],
        int(event.get_user_id()),
        NGM[state["mode"]],
        mapid=state["para"],
        mods=state["mods"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await UniMessage.text(data).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)
