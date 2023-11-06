from io import BytesIO
from typing import Union

from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11.helpers import ImageURLs
from nonebot.adapters.red import (
    MessageSegment as RedMessageSegment,
    Bot as RedBot,
    GroupMessageEvent as RedGroupMessageEvent,
    MessageEvent as RedMessageEvent,
)
from nonebot.adapters.onebot.v11 import (
    MessageEvent as v11MessageEvent,
    MessageSegment as v11MessageSegment,
    Bot as v11Bot,
    GroupMessageEvent as v11GroupMessageEvent,
)
from nonebot.typing import T_State
from ..file import user_cache_path, save_info_pic, safe_async_get
from nonebot_plugin_guild_patch import GuildMessageEvent


from .utils import split_msg

update_pic = on_command("更新背景", aliases={"更改背景"}, priority=11, block=True)
update_info = on_command("update", aliases={"更新"}, priority=11, block=True)


@update_pic.handle(parameterless=[split_msg()])
async def _(
    bot: v11Bot,
    state: T_State,
    event: v11GroupMessageEvent,
    pic_ls: list = ImageURLs("请在指令后附上图片"),
):
    if "error" in state:
        await update_pic.finish(
            v11MessageSegment.reply(event.message_id) + state["error"]
        )
    user = state["user"]
    pic_url = pic_ls[0]
    await save_info_pic(user, pic_url)
    msg = f"自群{event.group_id}: {event.user_id}的更新背景申请" + v11MessageSegment.image(
        pic_url
    )
    for superuser in get_driver().config.superusers:
        await bot.send_private_msg(user_id=int(superuser), message=msg)
    await update_pic.finish(v11MessageSegment.reply(event.message_id) + "更新背景成功")


@update_pic.handle(parameterless=[split_msg()])
async def _(bot: RedBot, state: T_State, event: RedGroupMessageEvent):
    if "error" in state:
        await update_pic.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
    user = state["user"]
    for i in event.message:
        if i.type == "image":
            base_url = "https://gchat.qpic.cn/gchatpic_new/1/"
            raw_id = i.data["md5"].upper()
            img_url = (
                f"{base_url}{event.group_id}-{event.get_user_id()}-{raw_id}/0?term=3"
            )
            pic = await safe_async_get(img_url)
            pic = pic.content
            # pic = await bot.fetch(i)
            break
    else:
        await update_pic.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + "请在指令后附上图片"
        )
        return
    msg = f"收到来自群{event.peerUin}:{event.senderUin}的更新背景申请" + RedMessageSegment.image(
        pic
    )
    for superuser in get_driver().config.superusers:
        await bot.send_friend_message(superuser, msg)
    path = user_cache_path / str(user)
    if not path.exists():
        path.mkdir()
    with open(path / "info.png", "wb") as f:
        f.write(BytesIO(pic).getvalue())
    await update_pic.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + "更新背景成功"
    )


@update_info.handle(parameterless=[split_msg()])
async def _(state: T_State, event: Union[v11MessageEvent, GuildMessageEvent]):
    if "error" in state:
        await update_info.finish(
            v11MessageSegment.reply(event.message_id) + state["error"]
        )
    user = state["user"]
    path = user_cache_path / str(user) / "icon.png"
    gif_path = user_cache_path / str(user) / "icon.gif"
    if path.exists():
        path.unlink()
    if gif_path.exists():
        gif_path.unlink()
    await update_info.finish(v11MessageSegment.reply(event.message_id) + "个人信息更新成功")


@update_info.handle(parameterless=[split_msg()])
async def _(state: T_State, event: RedMessageEvent):
    if "error" in state:
        await update_info.finish(
            RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid)
            + state["error"]
        )
    user = state["user"]
    path = user_cache_path / str(user) / "icon.png"
    gif_path = user_cache_path / str(user) / "icon.gif"
    if path.exists():
        path.unlink()
    if gif_path.exists():
        gif_path.unlink()
    await update_info.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + "个人信息更新成功"
    )
