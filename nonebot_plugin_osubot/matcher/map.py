from typing import Union

from nonebot import on_command
from nonebot.adapters.red import (
    MessageSegment as RedMessageSegment,
    MessageEvent as RedMessageEvent,
)
from nonebot.adapters.onebot.v11 import (
    MessageEvent as v11MessageEvent,
    MessageSegment as v11MessageSegment,
)
from nonebot.typing import T_State
from nonebot_plugin_guild_patch import GuildMessageEvent

from .utils import split_msg
from ..draw import draw_map_info, draw_bmap_info

osu_map = on_command("map", priority=11, block=True)
bmap = on_command("bmap", priority=11, block=True)


@osu_map.handle(parameterless=[split_msg()])
async def _map(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    map_id = state["para"]
    mods = state["mods"]
    if not map_id:
        await osu_map.finish(v11MessageSegment.reply(event.message_id) + "请输入地图ID")
    elif not map_id.isdigit():
        await osu_map.finish(v11MessageSegment.reply(event.message_id) + "请输入正确的地图ID")
    m = await draw_map_info(map_id, mods)
    if isinstance(m, str):
        await osu_map.finish(v11MessageSegment.reply(event.message_id) + m)
    await osu_map.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(m)
    )


@osu_map.handle(parameterless=[split_msg()])
async def _map(state: T_State, event: RedMessageEvent):
    map_id = state["para"]
    mods = state["mods"]
    if not map_id:
        await osu_map.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请输入地图ID"
        )
    elif not map_id.isdigit():
        await osu_map.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请输入正确的地图ID"
        )
    m = await draw_map_info(map_id, mods)
    if isinstance(m, str):
        await osu_map.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + m
        )
    await osu_map.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(m)
    )


@bmap.handle(parameterless=[split_msg()])
async def _bmap(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    set_id = state["para"]
    if not set_id:
        await bmap.finish(v11MessageSegment.reply(event.message_id) + "请输入setID")
    if not set_id.isdigit():
        await bmap.finish(v11MessageSegment.reply(event.message_id) + "请输入正确的setID")
        return
    m = await draw_bmap_info(set_id)
    if isinstance(m, str):
        await bmap.finish(v11MessageSegment.reply(event.message_id) + m)
    await bmap.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(m)
    )


@bmap.handle(parameterless=[split_msg()])
async def _bmap(state: T_State, event: RedMessageEvent):
    set_id = state["para"]
    if not set_id:
        await bmap.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请输入setID"
        )
    if not set_id.isdigit():
        await bmap.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请输入正确的setID"
        )
        return
    m = await draw_bmap_info(set_id)
    if isinstance(m, str):
        await bmap.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + m
        )
    await bmap.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(m)
    )
