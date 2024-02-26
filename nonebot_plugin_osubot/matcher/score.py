from arclet.alconna import Alconna, CommandMeta, Args
from nonebot_plugin_alconna import on_alconna, UniMessage
from nonebot.typing import T_State
from .utils import split_msg
from ..draw import get_score_data
from ..utils import NGM


score = on_alconna(
    Alconna(
        "score",
        Args["arg?", str],
        meta=CommandMeta(example="/score 图号"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)


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
