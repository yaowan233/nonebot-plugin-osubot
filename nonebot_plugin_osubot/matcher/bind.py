import asyncio
from arclet.alconna import Alconna, Args, CommandMeta
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import on_alconna, UniMessage, Match

from ..info import bind_user_info
from ..database import UserData


bind = on_alconna(
    Alconna(
        "bind",
        Args["name?", str],
        meta=CommandMeta(example="/bind peppy"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)
unbind = on_alconna(
    Alconna(
        "unbind",
        meta=CommandMeta(example="/unbind"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)
lock = asyncio.Lock()


@bind.handle()
async def _bind(name: Match[str], event: Event):
    name = name.result.strip() if name.available else ""
    if not name:
        await UniMessage.text("请在指令后输入您的 osuid").send(reply_to=True)
        return
    async with lock:
        if user := await UserData.get_or_none(user_id=event.get_user_id()):
            await UniMessage.text(f"您已绑定{user.osu_name}，如需要解绑请输入/unbind").send(
                reply_to=True
            )
            return
        msg = await bind_user_info("bind", name, event.get_user_id(), True)
    await UniMessage.text(msg).send(reply_to=True)


@unbind.handle()
async def _unbind(event: Event):
    if _ := await UserData.get_or_none(user_id=event.get_user_id()):
        await UserData.filter(user_id=event.get_user_id()).delete()
        await UniMessage.text("解绑成功！").send(reply_to=True)
    else:
        await UniMessage.text("尚未绑定，无需解绑").send(reply_to=True)
