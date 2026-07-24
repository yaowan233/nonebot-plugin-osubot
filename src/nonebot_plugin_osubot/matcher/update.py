from nonebot.typing import T_State
from nonebot import on_command
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from ..file import user_cache_path

update_info = on_command("update", priority=11, block=True, aliases={"更新信息"})


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
