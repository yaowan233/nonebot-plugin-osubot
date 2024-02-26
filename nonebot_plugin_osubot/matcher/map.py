from arclet.alconna import Alconna, Args, CommandMeta
from nonebot_plugin_alconna import on_alconna, UniMessage
from nonebot.typing import T_State

from .utils import split_msg
from ..draw import draw_map_info, draw_bmap_info

osu_map = on_alconna(
    Alconna(
        "map",
        Args["arg?", str],
        meta=CommandMeta(example="/map 图号"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)
bmap = on_alconna(
    Alconna(
        "bmap",
        Args["arg?", str],
        meta=CommandMeta(example="/bmap 图号"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)


@osu_map.handle(parameterless=[split_msg()])
async def _map(state: T_State):
    map_id = state["para"]
    mods = state["mods"]
    if not map_id:
        await UniMessage.text("请输入地图ID").send(reply_to=True)
        return
    elif not map_id.isdigit():
        await UniMessage.text("请输入正确的地图ID").send(reply_to=True)
        return
    m = await draw_map_info(map_id, mods)
    if isinstance(m, str):
        await UniMessage.text(m).send(reply_to=True)
        return
    await UniMessage.image(raw=m).send(reply_to=True)


@bmap.handle(parameterless=[split_msg()])
async def _bmap(state: T_State):
    set_id = state["para"]
    if not set_id:
        await UniMessage.text("请输入setID").send(reply_to=True)
        return
    if not set_id.isdigit():
        await UniMessage.text("请输入正确的setID").send(reply_to=True)
        return
    m = await draw_bmap_info(set_id)
    if isinstance(m, str):
        await UniMessage.text(m).send(reply_to=True)
        return
    await UniMessage.image(raw=m).send(reply_to=True)
