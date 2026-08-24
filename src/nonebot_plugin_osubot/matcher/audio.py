from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from .map_context import get_last_map_id, get_last_set_id
from ..api import get_beatmapset_preview_audio, get_preview_audio, osu_api
from ..exceptions import NetworkError

audio_preview = on_command("au", priority=11, block=True)


async def _bid_to_sid(bid: int) -> int | None:
    """将谱面 ID(bid) 转换为谱面集 ID(sid)，失败返回 None。"""
    try:
        data = await osu_api("map", map_id=bid)
    except NetworkError:
        return None
    sid = data.get("beatmapset_id")
    return int(sid) if sid else None


async def _fetch_voice(raw_id: int) -> bytes | None:
    """
    优先将 raw_id 视为 bid，按具体谱面拉取音频；
    仅在它不是有效 bid 时，才将其视为 sid 拉取谱面集默认音频。
    """
    sid = await _bid_to_sid(raw_id)
    if sid is not None:
        return await get_preview_audio(raw_id)
    return await get_beatmapset_preview_audio(raw_id)


@audio_preview.handle(parameterless=[split_msg()])
async def _audio(event: Event, state: T_State):
    raw = state.get("target")
    try:
        explicit_id = int(raw) if raw else None
    except (TypeError, ValueError):
        await UniMessage.text("无效的地图ID，请输入数字ID").finish(reply_to=True)
        return

    voice: bytes | None = None
    try:
        if explicit_id:
            voice = await _fetch_voice(explicit_id)
        else:
            # 未带 ID 时复用上下文：优先上一次 map 的 bid，其次上一次 bmap 的 sid
            last_map = get_last_map_id(event)
            if last_map:
                voice = await _fetch_voice(last_map)
            if not voice:
                last_set = await get_last_set_id(event)
                if last_set:
                    voice = await get_beatmapset_preview_audio(last_set)
    except NetworkError as e:
        await UniMessage.text(f"谱面试听失败：{str(e)}").finish(reply_to=True)
        return

    if not voice:
        await UniMessage.text("无法获取该谱面的音频，请检查ID是否正确，或先查询一张谱面后再试听").finish(reply_to=True)
        return

    await UniMessage.voice(raw=voice).finish()
