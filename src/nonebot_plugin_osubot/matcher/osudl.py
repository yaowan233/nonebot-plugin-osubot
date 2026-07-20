from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

from .map_context import get_last_set_id, remember_set
from ..api import osu_api
from ..utils import extract_beatmap_id, extract_beatmapset_id
from ..file import download_map, upload_file_stream_batch

osudl = on_command("osudl", aliases={"dl"}, priority=11, block=True)


@osudl.handle()
async def _osudl(bot: Bot, event: GroupMessageEvent, setid: Message = CommandArg()):
    raw_set_id = setid.extract_plain_text().strip()
    explicit_set_id = extract_beatmapset_id(raw_set_id)
    if not explicit_set_id and (linked_map_id := extract_beatmap_id(raw_set_id)):
        map_data = await osu_api("map", map_id=int(linked_map_id))
        explicit_set_id = str(map_data["beatmapset_id"])
    explicit_set_id = explicit_set_id or raw_set_id
    setid = explicit_set_id or await get_last_set_id(event)
    if not setid or not setid.isdigit():
        await UniMessage.text("请输入正确的setID，或先查询一张谱面").finish(reply_to=True)
    osz_path = await download_map(int(setid))
    if explicit_set_id:
        remember_set(event, setid)
    server_osz_path = await upload_file_stream_batch(bot, osz_path)
    try:
        await bot.call_api("upload_group_file", group_id=event.group_id, file=server_osz_path, name=osz_path.name)
    except Exception:
        await UniMessage.text("上传文件失败，可能是群空间满或没有权限导致的").send(reply_to=True)
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...
