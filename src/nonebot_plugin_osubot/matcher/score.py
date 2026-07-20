from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from .map_context import get_last_map_id, remember_map
from ..draw import get_score_data
from ..exceptions import NetworkError

score = on_command("score", aliases={"sc"}, priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    explicit_map_id = state["target"]
    map_id = explicit_map_id or get_last_map_id(event)
    if not map_id:
        await UniMessage.text("请输入谱面ID，或先查询一张谱面").finish(reply_to=True)
    try:
        data = await get_score_data(
            state["user"],
            state["is_lazer"],
            NGM[state["mode"]],
            state["mods"],
            map_id,
            state["source"],
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式 {lazer_mode}{mods} 成绩时 {str(e)}"
        ).finish(reply_to=True)
    if explicit_map_id:
        remember_map(event, map_id)
    await UniMessage.image(raw=data).finish(reply_to=True)
