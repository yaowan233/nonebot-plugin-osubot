from nonebot import on_command, get_driver, Bot
from nonebot.internal.adapter import Event
from nonebot.typing import T_State
from nonebot_plugin_alconna import (
    UniMessage,
    image_fetch,
    Target,
    SupportScope,
    UniMsg,
)
from nonebot_plugin_alconna.uniseg import Image
from nonebot_plugin_waiter import waiter

from .utils import split_msg
from ..database import UserData
from ..file import user_cache_path, save_info_pic

update_pic = on_command("更新背景", priority=11, block=True, aliases={"更改背景"})
update_info = on_command("update", priority=11, block=True, aliases={"更新信息"})
clear_background = on_command("清空背景", priority=11, block=True, aliases={"清除背景", "重置背景"})


@update_pic.handle()
async def _(event: Event, bot: Bot, state: T_State):
    qq = event.get_user_id()
    user_data = await UserData.get_or_none(user_id=int(qq))
    state["user"] = user_data.osu_id if user_data else 0
    if state["user"] == 0:
        await UniMessage.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号").finish(reply_to=True)
    await UniMessage.text("请发送图片").send(reply_to=True)

    @waiter(waits=["message"], keep_session=True)
    async def check(pic: UniMsg):
        return pic

    async for resp in check(timeout=60, retry=5, prompt="输入错误，请发送图片。剩余次数：{count}"):
        if resp is None:
            await update_pic.finish("等待超时")
            break
        if not resp.has(Image):
            continue
        pic = await image_fetch(event, bot, state, resp.get(Image)[0])
        if not pic:
            await UniMessage.text("图片下载失败，请重新发送").send()
            continue
        await save_info_pic(str(state["user"]), pic)
        msg = f"收到自{event.get_user_id()}的更新背景申请" + UniMessage.image(raw=pic)
        for superuser in get_driver().config.superusers:
            await Target.user(superuser, SupportScope.qq_client).send(msg)
        await UniMessage.text("更新背景成功").send()
        break
    else:
        await update_pic.finish("输入失败")


@update_info.handle(parameterless=[split_msg()])
async def _(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    user = state["user"]
    user_path = user_cache_path / str(user)
    for file_path in user_path.glob("icon*.*"):
        # 检查文件是否为图片格式
        if file_path.suffix.lower() in [".jpg", ".png", ".jpeg", ".gif", ".bmp", ".peg"]:
            file_path.unlink()
    await UniMessage.text("个人信息更新成功").send(reply_to=True)


@clear_background.handle(parameterless=[split_msg()])
async def _(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    user = state["user"]
    path = user_cache_path / str(user) / "info.png"
    if path.exists():
        path.unlink()
        await UniMessage.text("背景图片清除成功").send(reply_to=True)
        return
    else:
        await UniMessage.text("您还没有设置背景或已成功清除背景").send(reply_to=True)
