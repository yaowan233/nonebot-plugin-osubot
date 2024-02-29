from arclet.alconna import Alconna, Args, CommandMeta
from nonebot_plugin_alconna import (
    on_alconna,
    UniMessage,
    AlconnaMatch,
    image_fetch,
    Match,
    AlconnaMatcher,
)
from nonebot_plugin_alconna.uniseg import Image
from nonebot.typing import T_State
from ..file import user_cache_path, save_info_pic, safe_async_get


from .utils import split_msg

update_pic = on_alconna(
    Alconna(
        "更新背景",
        Args["img?", Image],
        meta=CommandMeta(example="/更新背景 [图片]"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
    aliases=("更改背景",),
)
update_info = on_alconna(
    Alconna(
        "update",
        meta=CommandMeta(example="/update"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
    aliases=("更新信息",),
)
clear_background = on_alconna(
    Alconna(
        "清空背景",
        meta=CommandMeta(example="/清空背景"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
    aliases=("清除背景", "重置背景"),
)


@update_pic.handle(parameterless=[split_msg()])
async def _(state: T_State, img: Match[bytes] = AlconnaMatch("img", image_fetch)):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    if not img.available:
        await UniMessage.text("请在指令之后附上图片").send(reply_to=True)
        return
    user = state["user"]
    pic_url = img.result
    await save_info_pic(user, pic_url)
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
