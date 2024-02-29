from arclet.alconna import Alconna, Args, CommandMeta
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import on_alconna, UniMessage, Match

from ..database import UserData
from ..utils import NGM


update_mode = on_alconna(
    Alconna(
        "更新模式",
        Args["mode?", int],
        meta=CommandMeta(example="/更新模式 3"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)


@update_mode.handle()
async def _(mode: Match[int], event: Event):
    mode = mode.result if mode.available else None
    user = await UserData.get_or_none(user_id=event.get_user_id())
    if not user:
        await UniMessage.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号").send(reply_to=True)
        return
    elif not mode:
        await UniMessage.text("请输入需要更新内容的模式").send(reply_to=True)
        return
    if 0 <= mode < 4:
        await UserData.filter(user_id=event.get_user_id()).update(osu_mode=mode)
        msg = f"已将默认模式更改为 {NGM[str(mode)]}"
    else:
        msg = "请输入正确的模式 0-3"
    await UniMessage.text(msg).send(reply_to=True)
