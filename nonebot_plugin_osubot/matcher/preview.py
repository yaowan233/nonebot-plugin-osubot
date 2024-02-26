from arclet.alconna import Alconna, Args, CommandMeta
from nonebot_plugin_alconna import on_alconna, UniMessage, Match, AlcResult
from ..mania import generate_preview_pic
from ..api import osu_api
from ..file import download_tmp_osu

generate_preview = on_alconna(
    Alconna(
        "preview",
        Args["osu_id?", str],
        meta=CommandMeta(example="/preview 4001513"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
    aliases={'预览', '完整预览'}
)


@generate_preview.handle()
async def _(
    osu_id: Match[str],
    result: AlcResult
):
    osu_id = osu_id.result.strip() if osu_id.available else ''
    if not osu_id or not osu_id.isdigit():
        await UniMessage("请输入正确的地图mapID").send(reply_to=True)
        return
    data = await osu_api("map", map_id=int(osu_id))
    if not data:
        await UniMessage.text("未查询到该地图").send(reply_to=True)
        return
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
    osu = await download_tmp_osu(osu_id)
    if result.source.command == "完整预览":
        pic = await generate_preview_pic(osu, True)
    else:
        pic = await generate_preview_pic(osu)
    await UniMessage.image(raw=pic).send(reply_to=True)
