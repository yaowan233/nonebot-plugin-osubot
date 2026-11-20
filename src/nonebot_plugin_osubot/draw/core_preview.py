"""In-process adapter for the PyO3 osu! beatmap preview renderer."""

from __future__ import annotations

import asyncio
from decimal import Decimal
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
from ..schema.score import Mod
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
_RATE_MODS = {"DT", "NC", "HT", "DC"}
# 猜歌按核心的 PNG/GIF 支持范围保留谱面效果，未知 Mod 不影响出题。
_GUESS_PNG_MODS = (
    {"EZ", "HR", "HD", "FL", "DA", "TC", "MR"},
    {"EZ", "HR", "SW"},
    {"EZ", "HR", "MR"},
    {"DS", "IN", "HO", "MR", *(f"{keys}K" for keys in range(1, 11))},
)
_GUESS_GIF_MODS = (set(), {"HD", "FL", "CS"}, {"HD", "FL"}, {"HD", "FL", "FI", "CS"})
_DA_SETTINGS = (
    ("circle_size", "CS", 0),
    ("approach_rate", "AR", -10),
    ("overall_difficulty", "OD", 0),
    ("drain_rate", "HP", 0),
)
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


def _mod_number(value: object, minimum: float, maximum: float) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
        return ""
    return format(Decimal(str(value)), "f")


def guess_preview_options(mods: Sequence[Mod], mode: int, want_gif: bool) -> tuple[PreviewFormat, list[str]]:
    acronyms = {mod.acronym.upper() for mod in mods}
    gif_only = _GUESS_GIF_MODS[mode] | _RATE_MODS
    fmt: PreviewFormat = "gif" if want_gif or mode == 0 or acronyms & gif_only else "png"
    supported = _GUESS_PNG_MODS[mode]
    if fmt == "gif":
        supported = supported | gif_only

    tokens: dict[str, str] = {}
    for mod in mods:
        code = mod.acronym.upper()
        if code not in supported:
            continue
        settings = mod.settings or {}
        if code in _RATE_MODS:
            # stable 成绩可能同时带 DT 和 NC，保留带变调效果的 NC。
            if (code == "DT" and "NC" in acronyms) or (code == "HT" and "DC" in acronyms):
                continue
            if tokens.keys() & _RATE_MODS:
                continue
            minimum, maximum = (1.01, 2.0) if code in {"DT", "NC"} else (0.5, 0.99)
            base = {"NC": "DT", "DC": "HT"}.get(code)
            rate = settings.get("speed_change")
            if rate is None and base in acronyms:
                rate = next((item.settings or {}).get("speed_change") for item in mods if item.acronym.upper() == base)
            tokens[code] = code + _mod_number(rate, minimum, maximum)
        elif code == "DA":
            params = []
            for field, suffix, minimum in _DA_SETTINGS:
                if value := _mod_number(settings.get(field), minimum, 11):
                    params.append(suffix + value)
            if params and not acronyms & {"EZ", "HR"}:
                tokens[code] = code + "".join(params)
        elif code == "MR" and mode == 0 and "HR" in acronyms:
            continue
        elif mode == 3 and (
            code == "HO"
            and "IN" in acronyms
            or code == "FL"
            and "HD" in acronyms
            or code == "FI"
            and acronyms & {"HD", "FL"}
            or code.endswith("K")
            and any(key.endswith("K") for key in tokens)
        ):
            continue
        else:
            tokens[code] = code
    return fmt, list(tokens.values())


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
