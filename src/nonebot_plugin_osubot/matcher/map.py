from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from .map_context import get_last_map_id, get_last_set_id, remember_map, remember_set
from ..exceptions import NetworkError
from ..draw import draw_map_info, draw_bmap_info

osu_map = on_command("map", aliases={"m"}, priority=11, block=True)
bmap = on_command("bmap", aliases={"bm"}, priority=11, block=True)


@osu_map.handle(parameterless=[split_msg()])
async def _map(event: Event, state: T_State):
    explicit_map_id = state["target"]
    map_id = explicit_map_id or get_last_map_id(event)
    mods = state["mods"]
    if not map_id:
        await UniMessage.text("请输入地图ID，或先查询一张谱面").finish(reply_to=True)
    try:
        m = await draw_map_info(map_id, mods)
    except NetworkError as e:
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(f"在查找地图mapid:{map_id}{mods}时 {str(e)}").finish(reply_to=True)
    if explicit_map_id:
        remember_map(event, map_id)
    await UniMessage.image(raw=m).finish(reply_to=True)


@bmap.handle(parameterless=[split_msg()])
async def _bmap(event: Event, state: T_State):
    explicit_set_id = state["target"]
    set_id = explicit_set_id
    try:
        if not set_id:
            set_id = await get_last_set_id(event)
        if not set_id:
            await UniMessage.text("请输入setID，或先查询一张谱面").finish(reply_to=True)
        m = await draw_bmap_info(set_id)
    except NetworkError as e:
        mods = f" mod:{state['mods']}" if state["mods"] else ""
        await UniMessage.text(f"在查找地图setid:{set_id}{mods}时 {str(e)}").finish(reply_to=True)
    if explicit_set_id:
        remember_set(event, set_id)
    await UniMessage.image(raw=m).finish(reply_to=True)
