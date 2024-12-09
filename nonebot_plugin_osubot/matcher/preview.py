from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from ..api import osu_api
from .utils import split_msg
from ..file import download_tmp_osu
from ..exceptions import NetworkError
from ..mania import generate_preview_pic
from ..draw.catch_preview import draw_cath_preview

generate_preview = on_command("预览", aliases={"preview", "完整预览"}, priority=11, block=True)


@generate_preview.handle(parameterless=[split_msg()])
async def _(state: T_State):
    osu_id = state["target"]
    if not osu_id or not osu_id.isdigit():
        await UniMessage.text("请输入正确的地图mapID").finish(reply_to=True)
    try:
        data = await osu_api("map", map_id=int(osu_id))
    except NetworkError as e:
        await UniMessage.text(f"查找map_id:{osu_id} 信息时 {str(e)}").finish(reply_to=True)
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
    elif not (0 <= int(state["mode"]) <= 3):
        await UniMessage.text("模式应为0-3！\n0: std\n1:taiko\n2:ctb\n3: mania").finish()
    else:
        await UniMessage.text(f"{NGM[state['mode']]}模式暂不支持预览").finish()
