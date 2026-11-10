"""Receive replay message attachments and OneBot group upload notices."""

from nonebot import on_message, on_notice
from nonebot.typing import T_State
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_apscheduler import scheduler

from ..draw.replay import ReplayPreview, replay_summary
from ..draw.core_preview import read_core_output
from ..replay_uploads import (
    UPLOAD_LIMITS,
    ReplayUploadOptions,
    replay_attachments,
    get_replay_upload,
    analyse_replay_upload,
    store_replay_attachments,
    cleanup_replay_uploads,
)


def replay_result_message(preview: ReplayPreview) -> UniMessage:
    raw = read_core_output(preview.path)
    message = UniMessage.text(replay_summary(preview) + "\n")
    if preview.path.suffix.lower() == ".mp4":
        return message + UniMessage.video(raw=raw, name=preview.path.name)
    return message + UniMessage.image(raw=raw)


async def accept_replay_attachments(bot: Bot, event: Event, state: T_State) -> bool:
    if event.get_type() != "message" and getattr(event, "notice_type", None) != "group_upload":
        return False
    if event.get_user_id() == str(bot.self_id):
        return False
    files = [item for item in await replay_attachments(bot, event) if item.suffix in UPLOAD_LIMITS]
    if not files:
        return False
    if not any(item.suffix == ".osr" for item in files) and get_replay_upload(bot, event) is None:
        return False
    state["replay_attachments"] = files
    return True


replay_file_message = on_message(rule=accept_replay_attachments, priority=12, block=True)
replay_file_notice = on_notice(rule=accept_replay_attachments, priority=12, block=True)


async def receive_replay_attachments(bot: Bot, event: Event, state: T_State):
    try:
        session = get_replay_upload(bot, event, create=True)
        async with session.processing_lock:
            files = state["replay_attachments"]
            await store_replay_attachments(bot, event, files)
            if not any(item.suffix == ".osr" for item in files):
                await UniMessage.text(
                    "已暂存谱面资源，请继续发送 .osr；若回放已上传，可发送 /ra 本地 重新分析。"
                ).send()
                return
            await UniMessage.text("已收到回放，正在分析，请稍候…").send()
            preview = await analyse_replay_upload(bot, event)
            await replay_result_message(preview).send()
    except Exception as error:
        await UniMessage.text(f"回放文件分析失败：{error}\n自制或已修改谱面可上传匹配的 .osu，再发送 /ra 本地。").send()


replay_file_message.handle()(receive_replay_attachments)
replay_file_notice.handle()(receive_replay_attachments)


@scheduler.scheduled_job("interval", seconds=60, id="osubot-replay-upload-cleanup")
async def expire_replay_attachments():
    cleanup_replay_uploads()


def upload_options(query) -> ReplayUploadOptions:
    if query.score_id or query.user or query.bid or query.mode or query.score_select or query.include_fails:
        raise ValueError("本地回放只接受输出格式和时间区间，模式及 Mods 从 .osr 读取")
    return ReplayUploadOptions(query.fmt, query.times, query.duration)
