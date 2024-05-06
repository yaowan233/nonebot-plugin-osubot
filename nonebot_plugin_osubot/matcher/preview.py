from nonebot import on_command
from nonebot.internal.adapter import Message
from nonebot.params import CommandArg
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..mania import generate_preview_pic
from ..api import osu_api
from ..file import download_tmp_osu

generate_preview = on_command(
    "预览", aliases={"preview", "完整预览"}, priority=11, block=True
)


@generate_preview.handle()
async def _(
    state: T_State,
    args: Message = CommandArg(),
):
    osu_id = args.extract_plain_text().strip()
    if not osu_id or not osu_id.isdigit():
        await UniMessage.text("请输入正确的地图mapID").finish(reply_to=True)
    data = await osu_api("map", map_id=int(osu_id))
    if not data:
        await UniMessage.text("未查询到该地图").finish(reply_to=True)
    if isinstance(data, str):
        await UniMessage.text(data).finish(reply_to=True)
    osu = await download_tmp_osu(osu_id)
    if state["_prefix"]["command"][0] == "完整预览":
        pic = await generate_preview_pic(osu, True)
    else:
        pic = await generate_preview_pic(osu)
    await UniMessage.image(raw=pic).finish(reply_to=True)
