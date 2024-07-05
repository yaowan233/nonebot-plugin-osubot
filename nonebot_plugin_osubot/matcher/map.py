from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from ..draw import draw_map_info, draw_bmap_info

osu_map = on_command("map", priority=11, block=True)
bmap = on_command("bmap", priority=11, block=True)


@osu_map.handle(parameterless=[split_msg()])
async def _map(state: T_State):
    map_id = state["para"]
    mods = state["mods"]
    if not map_id:
        await UniMessage.text("请输入地图ID").finish(reply_to=True)
    elif not map_id.isdigit():
        await UniMessage.text("请输入正确的地图ID").finish(reply_to=True)
    m = await draw_map_info(map_id, mods)
    if isinstance(m, str):
        await UniMessage.text(m).finish(reply_to=True)
    await UniMessage.image(raw=m).finish(reply_to=True)


@bmap.handle(parameterless=[split_msg()])
async def _bmap(state: T_State):
    set_id = state["para"]
    if not set_id:
        await UniMessage.text("请输入setID").finish(reply_to=True)
    if not set_id.isdigit():
        await UniMessage.text("请输入正确的setID").finish(reply_to=True)
    m = await draw_bmap_info(set_id)
    if isinstance(m, str):
        await UniMessage.text(m).finish(reply_to=True)
    await UniMessage.image(raw=m).finish(reply_to=True)
