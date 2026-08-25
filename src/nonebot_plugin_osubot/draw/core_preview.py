"""In-process adapter for the PyO3 osu! beatmap preview renderer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal
from collections.abc import Sequence

from nonebot import get_plugin_config
from osu_beatmap_preview import PreviewError, generate_preview_async

from ..config import Config

PreviewFormat = Literal["png", "gif", "mp4"]
ConvertMode = Literal["taiko", "ctb", "mania"]


class CorePreviewError(RuntimeError):
    """Raised when the native renderer cannot produce a usable artifact."""


_CONVERT_MAP: dict[int, ConvertMode] = {
    1: "taiko",
    2: "ctb",
    3: "mania",
}
_NON_OSU_MODS = {"GI", "F", "GIF"}
_plugin_config = get_plugin_config(Config)
_render_semaphore = asyncio.Semaphore(_plugin_config.osu_render_max_concurrency)


def mode_to_convert(source_mode: int | None, target_mode: int | None) -> ConvertMode | None:
    """Return a conversion only for standard maps targeting another ruleset."""
    if source_mode != 0 or target_mode in {None, 0, source_mode}:
        return None
    return _CONVERT_MAP.get(target_mode)


def mods_to_renderer(mods: Sequence[str] | None) -> str | None:
    """Normalize osubot mods while dropping the matcher-only GIF marker."""
    if not mods:
        return None
    cleaned = [mod.lower() for mod in mods if mod and mod.upper() not in _NON_OSU_MODS]
    return "+".join(cleaned) or None


async def render_with_core(
    beatmap_id: int | str,
    fmt: PreviewFormat,
    *,
    source_mode: int | None = None,
    target_mode: int | None = None,
    mods: Sequence[str] | None = None,
    time_range: str | None = None,
    fps: int | None = None,
) -> Path:
    """Render a preview in-process and return its validated output path."""
    try:
        async with _render_semaphore:
            result = await generate_preview_async(
                beatmap_id,
                format=fmt,
                convert=mode_to_convert(source_mode, target_mode),
                mods=mods_to_renderer(mods),
                times=time_range,
                fps=fps,
            )
        output = result.get("preview-img")
        if not isinstance(output, str) or not output:
            raise CorePreviewError("原生渲染结果缺少 preview-img")

        path = Path(output)
        if not path.is_file() or path.stat().st_size == 0:
            raise CorePreviewError(f"原生渲染产物不存在或为空: {path}")
        return path
    except CorePreviewError:
        raise
    except (PreviewError, OSError, TypeError, ValueError) as error:
        raise CorePreviewError(f"原生渲染失败: {error}") from error


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
