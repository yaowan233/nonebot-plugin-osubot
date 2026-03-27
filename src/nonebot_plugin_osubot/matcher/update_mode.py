from nonebot import on_command
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage
from nonebot.internal.adapter import Event, Message
from nonebot_plugin_orm import get_session
from sqlalchemy import select, update

from ..utils import NGM
from ..database import UserData

update_mode = on_command("更新模式", priority=11, block=True)
update_lazer = on_command("切换lazer", priority=11, block=True)


@update_mode.handle()
async def _(event: Event, mode: Message = CommandArg()):
    mode = mode.extract_plain_text().strip()
    async with get_session() as session:
        user = await session.scalar(select(UserData).where(UserData.user_id == event.get_user_id()))
        if not user:
            await UniMessage.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号").finish(reply_to=True)
        elif not mode:
            await UniMessage.text("请输入需要更新内容的模式").finish(reply_to=True)
        if mode.isdigit() and 0 <= int(mode) < 4:
            await session.execute(update(UserData).where(UserData.user_id == event.get_user_id()).values(osu_mode=int(mode)))
            await session.commit()
            msg = f"已将默认模式更改为 {NGM[mode]}"
        else:
            msg = "请输入正确的模式 0-3"
    await UniMessage.text(msg).finish(reply_to=True)


@update_lazer.handle()
async def _(event: Event):
    async with get_session() as session:
        user = await session.scalar(select(UserData).where(UserData.user_id == event.get_user_id()))
        if not user:
            await UniMessage.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号").finish(reply_to=True)
        await session.execute(
            update(UserData).where(UserData.user_id == event.get_user_id()).values(lazer_mode=not user.lazer_mode)
        )
        await session.commit()
    if user.lazer_mode:
        msg = "已关闭lazer模式"
    else:
        msg = "已开启lazer模式"
    await UniMessage.text(msg).finish(reply_to=True)
