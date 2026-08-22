from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from .map_context import get_last_map_id, get_last_set_id
from ..api import get_preview_audio, osu_api
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
    与 Kotlin 版 AudioService 的 fallback 逻辑保持一致：
    先视 raw_id 为 bid，转换为 sid 后拉取音频；
    若转换失败或音频拉取失败，再直接视 raw_id 为 sid 拉取。
    """
    sid = await _bid_to_sid(raw_id)
    if sid is not None:
        voice = await get_preview_audio(sid)
        if voice:
            return voice
    return await get_preview_audio(raw_id)


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
                    voice = await get_preview_audio(last_set)
    except NetworkError as e:
        await UniMessage.text(f"谱面试听失败：{str(e)}").finish(reply_to=True)
        return

    if not voice:
        await UniMessage.text("无法获取该谱面的音频，请检查ID是否正确，或先查询一张谱面后再试听").finish(reply_to=True)
        return

    if not voice:
        await UniMessage.text("无法获取该谱面的音频，请检查ID是否正确，或先查询一张谱面后再试听").finish(reply_to=True)
        return

    # ① 先发一条带引用的提示（保留 reply_to，让用户知道在回复谁）
    await UniMessage.text("🎵 谱面试听").send(reply_to=True)

    # ② 再单独发语音 —— 关键：这里不要 reply_to，避免 reply+record 同条触发渲染 bug
    await UniMessage.voice(raw=voice).finish()
