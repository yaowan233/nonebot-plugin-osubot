from nonebot import on_command
from nonebot.internal.adapter import Event, Message
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage

from ..database import UserData
from ..utils import NGM


update_mode = on_command("更新模式", priority=11, block=True)


@update_mode.handle()
async def _(
    event: Event,
    mode: Message = CommandArg()
):
    mode = mode.extract_plain_text().strip()
    user = await UserData.get_or_none(user_id=event.get_user_id())
    if not user:
        await UniMessage.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号").send(reply_to=True)
        return
    elif not mode:
        await UniMessage.text("请输入需要更新内容的模式").send(reply_to=True)
        return
    if mode.isdigit() and 0 <= int(mode) < 4:
        await UserData.filter(user_id=event.get_user_id()).update(osu_mode=int(mode))
        msg = f"已将默认模式更改为 {NGM[mode]}"
    else:
        msg = "请输入正确的模式 0-3"
    await UniMessage.text(msg).send(reply_to=True)
