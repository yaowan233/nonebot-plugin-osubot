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
from nonebot.internal.adapter import Message
from nonebot.params import CommandArg
from nonebot.typing import T_State

from ..mania import generate_preview_pic
from ..api import osu_api
from ..file import download_tmp_osu
from nonebot_plugin_guild_patch import GuildMessageEvent

generate_preview = on_command(
    "预览", aliases={"preview", "完整预览"}, priority=11, block=True
)


@generate_preview.handle()
async def _(
    event: Union[v11MessageEvent, GuildMessageEvent],
    state: T_State,
    args: Message = CommandArg(),
):
    osu_id = args.extract_plain_text().strip()
    if not osu_id or not osu_id.isdigit():
        await generate_preview.finish(
            v11MessageSegment.reply(event.message_id) + "请输入正确的地图mapID"
        )
    data = await osu_api("map", map_id=int(osu_id))
    if not data:
        await generate_preview.finish(
            v11MessageSegment.reply(event.message_id) + "未查询到该地图"
        )
    if isinstance(data, str):
        await generate_preview.finish(v11MessageSegment.reply(event.message_id) + data)
    osu = await download_tmp_osu(osu_id)
    if state["_prefix"]["command"][0] == "完整预览":
        pic = await generate_preview_pic(osu, True)
    else:
        pic = await generate_preview_pic(osu)
    await generate_preview.finish(
        v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(pic)
    )


@generate_preview.handle()
async def _(event: RedMessageEvent, state: T_State, args: Message = CommandArg()):
    osu_id = args.extract_plain_text().strip()
    if not osu_id or not osu_id.isdigit():
        await generate_preview.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请输入正确的地图mapID"
        )
    data = await osu_api("map", map_id=int(osu_id))
    if not data:
        await generate_preview.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "未查询到该地图"
        )
    if isinstance(data, str):
        await generate_preview.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + data
        )
    osu = await download_tmp_osu(osu_id)
    if state["_prefix"]["command"][0] == "完整预览":
        pic = await generate_preview_pic(osu, True)
    else:
        pic = await generate_preview_pic(osu)
    await generate_preview.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
        + RedMessageSegment.image(pic)
    )
