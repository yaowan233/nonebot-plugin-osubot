"""Short-lived replay attachments, isolated by bot, conversation and sender."""

from __future__ import annotations

import re
import uuid
import asyncio
import hashlib
import zipfile
from pathlib import Path
from io import BytesIO
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory

from expiringdict import ExpiringDict
from nonebot import get_plugin, get_plugin_config
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import File, UniMessage

from .network.manager import network_manager
from .draw.replay import ReplayPreview, render_replay_with_core
from .draw.core_preview import PreviewFormat

UPLOAD_LIMITS = {".osr": 64 * 1024**2, ".osu": 16 * 1024**2, ".osz": 128 * 1024**2}
UPLOAD_TTL = 600
_uploads: ExpiringDict = ExpiringDict(max_len=16, max_age_seconds=UPLOAD_TTL)
_recent_group_files: ExpiringDict = ExpiringDict(max_len=1024, max_age_seconds=30)


def _shared_balancer_enabled() -> bool:
    plugin = get_plugin("nonebot_plugin_bot_load_balancer")
    if plugin is None:
        return False
    try:
        return bool(get_plugin_config(plugin.module.Config).bot_load_balancer.enabled)
    except (AttributeError, TypeError, ValueError):
        return False


@dataclass(frozen=True)
class ReplayUploadOptions:
    fmt: PreviewFormat | None = None
    times: str | None = None
    duration: float | None = None


@dataclass
class ReplayAttachment:
    name: str
    url: str | None = None
    file_id: str | None = None
    busid: int | None = None
    size: int | None = None
    raw: bytes | BytesIO | None = None
    path: str | Path | None = None

    @property
    def suffix(self) -> str:
        return Path(self.name.replace("\\", "/")).suffix.lower()


@dataclass
class ReplayUploadSession:
    temporary: TemporaryDirectory = field(default_factory=lambda: TemporaryDirectory(prefix="osubot-replay-"))
    options: ReplayUploadOptions = field(default_factory=ReplayUploadOptions)
    replay: Path | None = None
    maps: dict[str, Path] = field(default_factory=dict)
    archive: Path | None = None
    resources_pending: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    processing_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def root(self) -> Path:
        return Path(self.temporary.name)


def replay_upload_key(bot: Bot, event: Event) -> tuple[str, ...]:
    user = event.get_user_id()
    if group := getattr(event, "group_id", None):
        conversation = f"group:{group}"
        bot_id = "__balanced_pool__" if _shared_balancer_enabled() else str(bot.self_id)
    elif channel := getattr(event, "channel_id", None):
        conversation = f"channel:{getattr(event, 'guild_id', '')}:{channel}"
        bot_id = str(bot.self_id)
    else:
        conversation = f"private:{user}"
        bot_id = str(bot.self_id)
    return bot.adapter.get_name(), bot_id, conversation, user


def claim_replay_attachments(bot: Bot, event: Event, attachments: list[ReplayAttachment]) -> list[ReplayAttachment]:
    """Claim duplicate OneBot group upload notices and messages as one event."""
    if bot.adapter.get_name() != "OneBot V11" or not getattr(event, "group_id", None):
        return attachments
    session_key = replay_upload_key(bot, event)
    unique = []
    for attachment in attachments:
        if not attachment.file_id:
            unique.append(attachment)
            continue
        key = (*session_key, str(attachment.file_id))
        if key in _recent_group_files:
            continue
        _recent_group_files[key] = True
        unique.append(attachment)
    return unique


def get_replay_upload(bot: Bot, event: Event, *, create: bool = False) -> ReplayUploadSession | None:
    key = replay_upload_key(bot, event)
    session = _uploads.get(key)
    if session is None and create:
        session = ReplayUploadSession()
    if session is not None and create:
        _uploads[key] = session
    return session


def cleanup_replay_uploads() -> None:
    # Reading expired keys drops their TemporaryDirectory owners. In-flight
    # operations retain their session, so cleanup cannot remove their inputs.
    for key in list(_uploads):
        _uploads.get(key)


async def replay_attachments(bot: Bot, event: Event) -> list[ReplayAttachment]:
    if getattr(event, "notice_type", None) == "group_upload":
        uploaded = event.file
        return [
            ReplayAttachment(
                uploaded.name,
                url=getattr(uploaded, "url", None),
                file_id=uploaded.id,
                busid=uploaded.busid,
                size=uploaded.size,
            )
        ]
    try:
        message = event.get_message()
    except (ValueError, NotImplementedError):
        return []
    if bot.adapter.get_name() == "OneBot V11":
        # NapCat/Lagrange file messages use several different field names.
        result = []
        for segment in message:
            if segment.type != "file":
                continue
            data = segment.data
            result.append(
                ReplayAttachment(
                    name=str(data.get("name") or data.get("file_name") or data.get("file") or "file.bin"),
                    url=data.get("url"),
                    file_id=data.get("file_id") or data.get("id"),
                    size=data.get("file_size") or data.get("size"),
                    busid=data.get("busid"),
                )
            )
        return result
    unified = await UniMessage.generate(message=message, event=event, bot=bot)
    return [ReplayAttachment(item.name, item.url, item.id, raw=item.raw, path=item.path) for item in unified.get(File)]


async def save_replay_attachment(bot: Bot, event: Event, attachment: ReplayAttachment, root: Path) -> Path:
    limit = UPLOAD_LIMITS.get(attachment.suffix)
    if limit is None:
        raise ValueError("仅支持 .osr、.osu 和 .osz 文件")
    if attachment.size is not None and int(attachment.size) > limit:
        raise ValueError(f"{attachment.suffix} 文件超过 {limit // 1024**2} MiB 限制")
    target = root / f"{uuid.uuid4().hex}{attachment.suffix}"
    total = 0

    def write(stream, chunk: bytes) -> None:
        nonlocal total
        total += len(chunk)
        if total > limit:
            raise ValueError(f"{attachment.suffix} 文件超过 {limit // 1024**2} MiB 限制")
        stream.write(chunk)

    try:
        with target.open("wb") as output:
            if attachment.raw is not None:
                raw = attachment.raw.getvalue() if isinstance(attachment.raw, BytesIO) else attachment.raw
                write(output, raw)
            elif attachment.path is not None:
                with Path(attachment.path).open("rb") as source:
                    while chunk := source.read(1024 * 1024):
                        write(output, chunk)
            else:
                url = attachment.url
                if not url and attachment.file_id and bot.adapter.get_name() == "OneBot V11":
                    group = getattr(event, "group_id", None)
                    if group is not None:
                        params = {"group_id": group, "file_id": attachment.file_id}
                        if attachment.busid is not None:
                            params["busid"] = attachment.busid
                        response = await bot.call_api("get_group_file_url", **params)
                    else:
                        try:
                            response = await bot.call_api(
                                "get_private_file_url", user_id=int(event.get_user_id()), file_id=attachment.file_id
                            )
                        except Exception:
                            response = await bot.call_api("get_file", file_id=attachment.file_id)
                    url = response.get("url")
                if not url or not url.startswith(("https://", "http://")):
                    raise ValueError("无法获取文件下载地址，请检查适配器的文件下载支持")
                client = await network_manager.get_client()
                async with client.stream("GET", url, timeout=60) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        write(output, chunk)
        if not total:
            raise ValueError("上传文件为空")
        return target
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def replay_beatmap_checksum(path: Path) -> str:
    # The first osu! string in the OSR header is the original beatmap MD5.
    # Read only the header; compressed replay data stays inside the renderer.
    with path.open("rb") as stream:
        header = stream.read(7)
        checksum = stream.read(32)
    if (
        len(header) != 7
        or header[0] > 3
        or header[5:] != b"\x0b\x20"
        or not re.fullmatch(rb"[0-9a-fA-F]{32}", checksum)
    ):
        raise ValueError("无效的 .osr 回放文件，缺少有效的谱面 MD5")
    return checksum.decode("ascii").lower()


async def store_replay_attachments(
    bot: Bot, event: Event, attachments: list[ReplayAttachment], options: ReplayUploadOptions | None = None
) -> ReplayUploadSession:
    session = get_replay_upload(bot, event, create=True)
    async with session.lock:
        # Process resources before OSR regardless of attachment order.
        for attachment in sorted(attachments, key=lambda item: item.suffix == ".osr"):
            if attachment.suffix not in UPLOAD_LIMITS:
                continue
            if sum(path.stat().st_size for path in session.root.iterdir() if path.is_file()) > 192 * 1024**2:
                raise ValueError("本次上传总量过大，请等待临时文件到期后重试")
            path = await save_replay_attachment(bot, event, attachment, session.root)
            try:
                if sum(item.stat().st_size for item in session.root.iterdir() if item.is_file()) > 192 * 1024**2:
                    raise ValueError("本次上传总量超过 192 MiB，请等待临时文件到期后重试")
                if attachment.suffix == ".osr":
                    checksum = replay_beatmap_checksum(path)
                    if session.replay and not session.resources_pending and checksum not in session.maps:
                        session.maps.clear()
                        session.archive = None
                    if session.replay:
                        session.replay.unlink(missing_ok=True)
                    session.replay = path
                    session.resources_pending = False
                elif attachment.suffix == ".osu":
                    content = path.read_bytes()
                    if not content.lstrip(b"\xef\xbb\xbf\r\n ").startswith(b"osu file format"):
                        raise ValueError("上传的 .osu 不是有效的谱面文件")
                    if len(session.maps) >= 8:
                        raise ValueError("一次最多暂存 8 个谱面文件")
                    session.maps[hashlib.md5(content).hexdigest()] = path
                    session.resources_pending = True
                else:
                    if not zipfile.is_zipfile(path):
                        raise ValueError("上传的 .osz 不是有效的谱面包")
                    if session.archive:
                        session.archive.unlink(missing_ok=True)
                    session.archive = path
                    session.resources_pending = True
            except Exception:
                path.unlink(missing_ok=True)
                raise
        if options is not None:
            session.options = options
        _uploads[replay_upload_key(bot, event)] = session
    return session


def _uploaded_map(session: ReplayUploadSession, checksum: str) -> Path | None:
    if path := session.maps.get(checksum):
        return path
    if session.archive is None:
        return None
    with zipfile.ZipFile(session.archive) as archive:
        maps = [info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith(".osu")]
        if len(maps) > 128 or sum(info.file_size for info in maps) > UPLOAD_LIMITS[".osu"]:
            raise ValueError("谱面包内的 .osu 文件数量或总大小超过限制")
        for info in maps:
            content = archive.read(info)
            if hashlib.md5(content).hexdigest() == checksum:
                path = session.root / f"{checksum}.osu"
                path.write_bytes(content)
                session.maps[checksum] = path
                return path
    raise ValueError("上传的 .osz 中没有与回放 MD5 匹配的谱面")


async def analyse_replay_upload(bot: Bot, event: Event, options: ReplayUploadOptions | None = None) -> ReplayPreview:
    session = get_replay_upload(bot, event)
    if session is None or session.replay is None:
        raise ValueError("当前会话没有你的 .osr 回放，请先上传文件；临时文件保留 10 分钟")

    task = asyncio.create_task(_analyse_session(session, options))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        task.add_done_callback(lambda finished: finished.exception() if not finished.cancelled() else None)
        raise


async def _analyse_session(session: ReplayUploadSession, options: ReplayUploadOptions | None) -> ReplayPreview:
    async with session.lock:
        checksum = replay_beatmap_checksum(session.replay)
        try:
            osu_file = _uploaded_map(session, checksum)
        except (zipfile.BadZipFile, RuntimeError) as error:
            raise ValueError(f"无法读取谱面包中的谱面：{error}") from error
        if session.maps and osu_file is None:
            raise ValueError("上传的 .osu 与回放 MD5 不匹配，请提供游玩时使用的原始谱面")
        selected = options or session.options
        preview = await render_replay_with_core(
            osr_file=session.replay,
            osu_file=osu_file,
            osz_file=session.archive,
            fmt=selected.fmt,
            times=selected.times,
            duration=selected.duration,
            output_dir=session.root / "outputs",
        )
        session.resources_pending = False
        return preview
