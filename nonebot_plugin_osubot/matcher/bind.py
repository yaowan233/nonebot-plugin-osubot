import asyncio

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage
from nonebot.internal.adapter import Event, Message

from ..api import get_uid_by_name
from ..info import bind_user_info
from ..exceptions import NetworkError
from ..database import UserData, SbUserData

bind = on_command("bind", priority=11, block=True)
unbind = on_command("unbind", priority=11, block=True)
sbbind = on_command("sbbind", priority=11, block=True)
sbunbind = on_command("sbunbind", priority=11, block=True)
lock = asyncio.Lock()


@bind.handle()
async def _bind(event: Event, name: Message = CommandArg()):
    name = name.extract_plain_text().strip()
    if not name:
        await UniMessage.text("请在指令后输入您的 osuid").finish(reply_to=True)
    async with lock:
        if user := await UserData.get_or_none(user_id=event.get_user_id()):
            await UniMessage.text(f"您已绑定{user.osu_name}，如需要解绑请输入/unbind").finish(reply_to=True)
        try:
            msg = await bind_user_info("bind", name, event.get_user_id())
        except NetworkError:
            await UniMessage.text(f"绑定失败，找不到叫 {name} 的人哦").finish(reply_to=True)
    await UniMessage.text(msg).finish(reply_to=True)


@sbbind.handle()
async def _(event: Event, name: Message = CommandArg()):
    name = name.extract_plain_text().strip()
    if not name:
        await UniMessage.text("请在指令后输入您的 osuid").finish(reply_to=True)
    async with lock:
        if user := await SbUserData.get_or_none(user_id=event.get_user_id()):
            await UniMessage.text(f"您已绑定{user.osu_name}，如需要解绑请输入/sbunbind").finish(reply_to=True)
        uid = await get_uid_by_name(name, "ppysb")
        await SbUserData.create(user_id=event.get_user_id(), osu_id=uid, osu_name=name)
    await UniMessage.text(f"成功绑定 ppysb 服务器用户： {name}").finish(reply_to=True)


@unbind.handle()
async def _unbind(event: Event):
    if _ := await UserData.get_or_none(user_id=event.get_user_id()):
        await UserData.filter(user_id=event.get_user_id()).delete()
        await UniMessage.text("解绑成功！").send(reply_to=True)
    else:
        await UniMessage.text("尚未绑定，无需解绑").send(reply_to=True)


@sbunbind.handle()
async def _(event: Event):
    if _ := await SbUserData.get_or_none(user_id=event.get_user_id()):
        await SbUserData.filter(user_id=event.get_user_id()).delete()
        await UniMessage.text("解绑成功！").send(reply_to=True)
    else:
        await UniMessage.text("尚未绑定，无需解绑").send(reply_to=True)
