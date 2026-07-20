from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Event, Message
from nonebot_plugin_alconna import UniMessage

from .map_context import get_last_map_id, remember_map
from ..utils import extract_beatmap_id
from ..info import get_bg
from ..exceptions import NetworkError

getbg = on_command("getbg", aliases={"bg"}, priority=11, block=True)


@getbg.handle()
async def _get_bg(event: Event, bg: Message = CommandArg()):
    raw_map_id = bg.extract_plain_text().strip()
    explicit_map_id = extract_beatmap_id(raw_map_id) or raw_map_id
    bg = explicit_map_id or get_last_map_id(event)
    if not bg:
        await UniMessage.text("请输入需要提取BG的地图ID，或先查询一张谱面").finish(reply_to=True)
    try:
        img = await get_bg(bg)
    except NetworkError as e:
        await UniMessage.text(f"获取图片时 {str(e)}").finish(reply_to=True)
    if explicit_map_id:
        remember_map(event, bg)
    from io import BytesIO

    byt = BytesIO()
    img.convert("RGB").save(byt, "jpeg")
    await UniMessage.image(raw=byt).finish(reply_to=True)
