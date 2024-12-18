from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from ..draw import get_score_data
from ..exceptions import NetworkError

score = on_command("score", priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if not state["target"]:
        await UniMessage.text("请输入谱面ID").finish(reply_to=True)
    try:
        data = await get_score_data(
            state["user"],
            state["is_lazer"],
            NGM[state["mode"]],
            state["mods"],
            state["target"],
            state["source"],
        )
    except NetworkError as e:
        lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式" f" {lazer_mode}{mods} 成绩时 {str(e)}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)
