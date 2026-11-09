"""In-process adapter for the PyO3 osu! beatmap preview renderer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal
from collections.abc import Sequence

from nonebot import get_plugin_config
from nonebot.log import logger
from osu_beatmap_preview import PreviewError, generate_preview_async

from ..api import osu_api
from ..file import ensure_osu_file
from ..config import Config
from ..exceptions import NetworkError
from .core_preview_recovery import recover_preview_download
from .core_preview_settings import native_render_config

PreviewFormat = Literal["png", "gif", "mp4"]
ConvertMode = Literal["taiko", "ctb", "mania"]


class CorePreviewError(RuntimeError):
    """Raised when the native renderer cannot produce a usable artifact."""


_CONVERT_MAP: dict[int, ConvertMode] = {
    1: "taiko",
    2: "ctb",
    3: "mania",
}
# GIF is a command marker; Classic is score metadata unsupported by the renderer.
_IGNORED_PREVIEW_MODS = {"GI", "F", "GIF", "CL"}
_plugin_config = get_plugin_config(Config)
_render_semaphore = asyncio.Semaphore(_plugin_config.osu_render_max_concurrency)


def mode_to_convert(source_mode: int | None, target_mode: int | None) -> ConvertMode | None:
    """Return a conversion only for standard maps targeting another ruleset."""
    if source_mode != 0 or target_mode in {None, 0, source_mode}:
        return None
    return _CONVERT_MAP.get(target_mode)


def mods_to_renderer(mods: Sequence[str] | None, fmt: PreviewFormat = "gif") -> str | None:
    """Normalize mods and omit speed changes unsupported by static previews."""
    if not mods:
        return None
    cleaned = [mod.lower() for mod in mods if mod and mod.upper() not in _IGNORED_PREVIEW_MODS]
    if fmt == "png":
        cleaned = [mod for mod in cleaned if mod not in {"dt", "ht"}]
    return "+".join(cleaned) or None


async def preview_cache_enabled(beatmap_id: int | str) -> bool:
    """Only ranked maps are stable enough to reuse rendered previews."""
    try:
        data = await osu_api("map", map_id=int(beatmap_id))
    except NetworkError:
        return False
    return data.get("status") == "ranked"


async def render_with_core(
    beatmap_id: int | str | None,
    fmt: PreviewFormat,
    *,
    source_mode: int | None = None,
    target_mode: int | None = None,
    mods: Sequence[str] | None = None,
    time_range: str | None = None,
    fps: int | None = None,
    osu_file: str | Path | None = None,
    osz_file: str | Path | None = None,
) -> Path:
    """Render a preview in-process and return its validated output path."""
    try:
        no_cache = True
        # Explicit local input must also work without osu! API access.
        if osu_file is None and osz_file is None and beatmap_id is not None:
            try:
                data = await osu_api("map", map_id=int(beatmap_id))
            except NetworkError:
                data = {}
            no_cache = data.get("status") != "ranked"
            # Standalone .osu input cannot supply the audio required by MP4.
            if fmt != "mp4" and data.get("beatmapset_id"):
                try:
                    osu_file = await ensure_osu_file(data["beatmapset_id"], beatmap_id, data.get("checksum"))
                except Exception as error:
                    raise CorePreviewError(f"读取或下载本地谱面失败: {error}") from error
        async with _render_semaphore:
            options = {
                "format": fmt,
                "convert": mode_to_convert(source_mode, target_mode),
                "mods": mods_to_renderer(mods, fmt),
                "times": time_range,
                "fps": fps,
                "no_cache": no_cache,
                "config": native_render_config(),
            }
            if osu_file is not None:
                options["osu_file"] = Path(osu_file).resolve()
            if osz_file is not None:
                options["osz_file"] = Path(osz_file).resolve()
            try:
                result = await generate_preview_async(beatmap_id, **options)
            except PreviewError as error:
                if (
                    osu_file is not None
                    or osz_file is not None
                    or fmt == "mp4"
                    or (f"failed to download beatmap {beatmap_id}:" not in str(error))
                ):
                    raise
                logger.warning("原生谱面下载失败，尝试插件下载源并重新渲染: {}", beatmap_id)
                try:
                    result = await recover_preview_download(beatmap_id, options)
                except Exception as recovery_error:
                    raise CorePreviewError(f"谱面下载恢复失败: {recovery_error}") from recovery_error
        return core_output_path(result)
    except CorePreviewError:
        raise
    except (PreviewError, NetworkError, OSError, TypeError, ValueError) as error:
        raise CorePreviewError(f"原生渲染失败: {error}") from error


def core_output_path(result: dict) -> Path:
    """Validate the common artifact field of beatmap and replay results."""
    output = result.get("preview-img")
    if not isinstance(output, str) or not output:
        raise CorePreviewError("原生渲染结果缺少 preview-img")
    path = Path(output)
    if not path.is_file() or path.stat().st_size == 0:
        raise CorePreviewError(f"原生渲染产物不存在或为空: {path}")
    return path


def read_core_output(path: Path) -> bytes:
    """Read a native artifact while preserving the adapter's error contract."""
    try:
        return path.read_bytes()
    except OSError as error:
        raise CorePreviewError(f"读取原生渲染产物失败: {error}") from error


def validate_core_output_readable(path: Path) -> None:
    """Stream through a native artifact so read failures can trigger fallback."""
    try:
        with path.open("rb") as stream:
            while stream.read(1024 * 1024):
                pass
    except OSError as error:
        raise CorePreviewError(f"读取原生渲染产物失败: {error}") from error
