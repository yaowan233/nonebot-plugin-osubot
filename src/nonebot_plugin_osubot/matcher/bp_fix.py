from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..draw.bp_fix import draw_bp_fix
from ..exceptions import NetworkError
from ..utils import NGM
from .utils import split_msg


bp_fix = on_command("fix", aliases={"bpfix", "理论fc"}, priority=11, block=True)


@bp_fix.handle(parameterless=[split_msg()])
async def _bp_fix(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    if state["mods"] or state["query"] or state["target"]:
        await UniMessage.text("BP Fix 只接受玩家和模式，例如：/fix peppy:o").finish(reply_to=True)
    try:
        data = await draw_bp_fix(
            state["user"],
            state["is_lazer"],
            NGM[state["mode"]],
            state["source"],
        )
    except NetworkError as error:
        await UniMessage.text(
            f"在分析用户：{state['username']} {NGM[state['mode']]} 模式 BP Fix 时 {error}"
        ).finish(reply_to=True)
    await UniMessage.image(raw=data).finish(reply_to=True)
