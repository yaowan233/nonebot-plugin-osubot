from arclet.alconna import Alconna, Args, CommandMeta
from nonebot import on_command
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import on_alconna, UniMessage, AlconnaMatch, image_fetch, Match
from nonebot_plugin_alconna.uniseg import Image
from nonebot.typing import T_State

from ..database import UserData
from ..file import user_cache_path, save_info_pic


from .utils import split_msg

update_pic = on_alconna(
    Alconna(
        "更新背景",
        Args["img?", Image],
        meta=CommandMeta(example="/更新背景 [图片]"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
    aliases=('更改背景',)
)
update_info = on_command("update", priority=11, block=True, aliases={'更新信息'})
clear_background = on_command("清空背景", priority=11, block=True, aliases={'清除背景', '重置背景'})


@update_pic.handle()
async def _(event: Event, state: T_State, img: Match[bytes] = AlconnaMatch("img", image_fetch)):
    qq = event.get_user_id()
    user_data = await UserData.get_or_none(user_id=int(qq))
    state["user"] = user_data.osu_id if user_data else 0
    if state["user"] == 0:
        await UniMessage.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号").send(reply_to=True)
        return
    if not img.available:
        await UniMessage.text("请在指令之后附上图片").send(reply_to=True)
        return
    user = state["user"]
    pic_url = img.result
    await save_info_pic(str(user), pic_url)
    # msg = f"自群{event.group_id}: {event.user_id}的更新背景申请" + UniMessage.image(url=pic_url)
    # for superuser in get_driver().config.superusers:
    #     await bot.send_private_msg(user_id=int(superuser), message=msg)
    await UniMessage.text("更新背景成功").send(reply_to=True)


@update_info.handle(parameterless=[split_msg()])
async def _(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    user = state["user"]
    path = user_cache_path / str(user) / "icon.png"
    gif_path = user_cache_path / str(user) / "icon.gif"
    if path.exists():
        path.unlink()
    if gif_path.exists():
        gif_path.unlink()
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
