from typing import Union
from nonebot_plugin_guild_patch import GuildMessageEvent
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
from .utils import split_msg
from ..draw import draw_score, draw_bp
from ..utils import NGM

bp = on_command("bp", priority=11, block=True)
pfm = on_command("pfm", priority=11, block=True)
tbp = on_command("tbp", aliases={"todaybp"}, priority=11, block=True)


@bp.handle(parameterless=[split_msg()])
async def _bp(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await bp.finish(v11MessageSegment.reply(event.message_id) + state["error"])
    if "-" in state["para"]:
        await _pfm(state, event)
    best = state["para"]
    if not best:
        best = "1"
    if not best.isdigit():
        await bp.finish(v11MessageSegment.reply(event.message_id) + "只能接受纯数字的bp参数")
    best = int(best)
    if best <= 0 or best > 100:
        await bp.finish(v11MessageSegment.reply(event.message_id) + "只允许查询bp 1-100 的成绩")
    data = await draw_score(
        "bp",
        state["user"],
        NGM[state["mode"]],
        best=best,
        mods=state["mods"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await bp.finish(v11MessageSegment.reply(event.message_id) + data)
    await bp.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(data)
    )


@bp.handle(parameterless=[split_msg()])
async def _bp(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await bp.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
    best = state["para"]
    if "-" in state["para"]:
        await _pfm1(state, event)
    if not best:
        best = "1"
    if not best.isdigit():
        await bp.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "只能接受纯数字的bp参数"
        )
    best = int(best)
    if best <= 0 or best > 100:
        await bp.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "只允许查询bp 1-100 的成绩"
        )
    data = await draw_score(
        "bp",
        state["user"],
        NGM[state["mode"]],
        best=best,
        mods=state["mods"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await bp.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + data
        )
    await bp.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(data)
    )


@pfm.handle(parameterless=[split_msg()])
async def _pfm(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await pfm.finish(v11MessageSegment.reply(event.message_id) + state["error"])
    ls = state["para"].split("-")
    low, high = ls[0], ls[1]
    if not low.isdigit() or not high.isdigit():
        await pfm.finish(v11MessageSegment.reply(event.message_id) + '参数应为 "数字-数字"的形式!')
        return
    low, high = int(low), int(high)
    if not 0 < low < high <= 100:
        await pfm.finish(v11MessageSegment.reply(event.message_id) + "仅支持查询bp1-100")
    data = await draw_bp(
        "bp",
        state["user"],
        NGM[state["mode"]],
        state["mods"],
        low,
        high,
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await pfm.finish(v11MessageSegment.reply(event.message_id) + data)
    await pfm.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(data)
    )


@pfm.handle(parameterless=[split_msg()])
async def _pfm1(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await pfm.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
    ls = state["para"].split("-")
    low, high = ls[0], ls[1]
    if not low.isdigit() or not high.isdigit():
        await pfm.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + '参数应为 "数字-数字"的形式!'
        )
        return
    low, high = int(low), int(high)
    if not 0 < low < high <= 100:
        await pfm.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "仅支持查询bp1-100"
        )
    data = await draw_bp(
        "bp",
        state["user"],
        NGM[state["mode"]],
        state["mods"],
        low,
        high,
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await pfm.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + data
        )
    await pfm.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(data)
    )


@tbp.handle(parameterless=[split_msg()])
async def _tbp(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await tbp.finish(v11MessageSegment.reply(event.message_id) + state["error"])
    data = await draw_bp(
        "tbp",
        state["user"],
        NGM[state["mode"]],
        [],
        day=state["day"],
        is_name=state["is_name"],
    )
    if isinstance(data, str):
        await tbp.finish(v11MessageSegment.reply(event.message_id) + data)
    await tbp.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(data)
    )


@tbp.handle(parameterless=[split_msg()])
async def _tbp(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await tbp.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
    data = await draw_bp(
        "tbp",
        state["user"],
        NGM[state["mode"]],
        [],
        day=state["day"],
         is_name=state["is_name"],
    )
    if isinstance(data, str):
        await tbp.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + data
        )
    await tbp.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(data)
    )
