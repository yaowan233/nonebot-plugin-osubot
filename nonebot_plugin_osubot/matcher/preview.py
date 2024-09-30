from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..api import osu_api
from .utils import split_msg
from ..file import download_tmp_osu
from ..mania import generate_preview_pic
from ..draw.catch_preview import draw_cath_preview

generate_preview = on_command("预览", aliases={"preview", "完整预览"}, priority=11, block=True)


@generate_preview.handle(parameterless=[split_msg()])
async def _(state: T_State):
    osu_id = state["para"]
    if not osu_id or not osu_id.isdigit():
        await UniMessage.text("请输入正确的地图mapID").finish(reply_to=True)
    data = await osu_api("map", map_id=int(osu_id))
    if not data:
        await UniMessage.text("未查询到该地图").finish(reply_to=True)
    if isinstance(data, str):
        await UniMessage.text(data).finish(reply_to=True)
    if state["mode"] == "3":
        osu = await download_tmp_osu(osu_id)
        if state["_prefix"]["command"][0] == "完整预览":
            pic = await generate_preview_pic(osu, True)
        else:
            pic = await generate_preview_pic(osu)
        await UniMessage.image(raw=pic).finish(reply_to=True)
    elif state["mode"] == "2":
        pic = await draw_cath_preview(int(osu_id), data["beatmapset_id"], state["mods"])
        await UniMessage.image(raw=pic).finish(reply_to=True)
    else:
        await UniMessage.text("该模式暂不支持预览").finish()
