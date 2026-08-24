import re
import time
import base64
import shutil
import asyncio
import hashlib
import tempfile
from io import BytesIO
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass
from typing import TypeVar, Optional
from collections.abc import Callable, Sequence, Awaitable

from nonebot.log import logger
from nonebot import get_plugin_config

from ..config import Config
from ..file import map_path
from .browser import persistent_page
from .utils import load_osu_file_and_setup_template
from .core_preview import (
    PreviewFormat,
    CorePreviewError,
    read_core_output,
    render_with_core,
)

template_path = str(Path(__file__).parent / "osu_preview_templates")
taiko_skin_files = {
    "taiko-roll-end.png",
    "taiko-roll-middle.png",
}
full_preview_chunk_duration = 5_000
taiko_full_preview_chunk_duration = 10_000
full_preview_cache_version = 9
plugin_config = get_plugin_config(Config)
_full_preview_locks: dict[Path, asyncio.Lock] = {}


@dataclass(slots=True)
class RenderedPreviewChunk:
    data: bytes
    preview_start: int
    preview_end: int
    actual_start: int
    actual_end: int


def _preview_mode(osu_file: str) -> int:
    match = re.search(r"(?m)^Mode\s*:\s*(\d+)\s*$", osu_file)
    return int(match.group(1)) if match else 0


def _convert_preview_mode(osu_file: str, target_mode: int | None) -> str:
    source_mode = _preview_mode(osu_file)
    if target_mode is None or target_mode == source_mode or source_mode != 0:
        return osu_file
    if target_mode == 3:
        from ..mania import convert_standard_to_mania_preview

        return "\n".join(convert_standard_to_mania_preview(osu_file).write())
    if target_mode in {1, 2}:
        mode_line = f"Mode: {target_mode}"
        if re.search(r"(?m)^Mode\s*:", osu_file):
            return re.sub(r"(?m)^Mode\s*:\s*\d+\s*$", mode_line, osu_file, count=1)
        return osu_file.replace("[General]", f"[General]\n{mode_line}", 1)
    return osu_file


def _configured_taiko_skin_path() -> Path | None:
    if plugin_config.osu_preview_taiko_skin_path is None:
        return None
    return Path(plugin_config.osu_preview_taiko_skin_path).expanduser()


def _full_preview_scale() -> float:
    return max(0.5, min(float(plugin_config.osu_preview_full_scale), 1.0))


def _full_preview_frame_interval() -> int:
    return max(20, min(int(plugin_config.osu_preview_full_frame_interval), 50))


def _taiko_full_preview_scale() -> float:
    return max(0.5, min(float(plugin_config.osu_preview_taiko_full_scale), 1.0))


def _taiko_full_preview_frame_interval() -> int:
    return max(20, min(int(plugin_config.osu_preview_taiko_full_frame_interval), 50))


def _std_catch_full_preview_scale() -> float:
    return max(0.5, min(float(plugin_config.osu_preview_std_catch_full_scale), 1.0))


def _std_catch_full_preview_frame_interval() -> int:
    return max(20, min(int(plugin_config.osu_preview_std_catch_full_frame_interval), 50))


async def load_taiko_skin_assets(skin_path: str | Path | None = None) -> dict[str, str]:
    """Load the small, explicitly supported subset from a global skin directory."""
    source_path = Path(skin_path).expanduser() if skin_path is not None else _configured_taiko_skin_path()
    if source_path is None or not source_path.is_dir():
        return {}

    entries = {path.name.casefold(): path for path in source_path.iterdir() if path.is_file()}
    assets: dict[str, str] = {}
    for filename in taiko_skin_files:
        asset_path = entries.get(filename) or entries.get(filename.replace(".png", "@2x.png"))
        if asset_path is None:
            continue
        encoded = base64.b64encode(asset_path.read_bytes()).decode()
        assets[filename] = f"data:image/png;base64,{encoded}"
    return assets


@lru_cache(maxsize=1)
def _worker_data_uri() -> str:
    worker_script_path = Path(template_path) / "gif.js" / "gif.worker.js"
    encoded = base64.b64encode(worker_script_path.read_bytes()).decode()
    return f"data:application/javascript;base64,{encoded}"


async def _render_gif_chunk(
    osu_file: str,
    template,
    taiko_skin_assets: dict[str, str],
    *,
    duration: int,
    start_time: int | None = None,
    use_map_start: bool = False,
    scale: float = 0.5,
    frame_time_span: int | None = None,
) -> RenderedPreviewChunk:
    img_selector = "img"
    base_url = Path(template_path).as_uri() + "/"
    html = await template.render_async(
        osu_file=osu_file,
        base_url=base_url,
        worker_data_uri=_worker_data_uri(),
        taiko_skin_assets=taiko_skin_assets,
        duration=duration,
        start_time=start_time,
        use_map_start=use_map_start,
        scale=scale,
        frame_time_span=frame_time_span,
    )

    async with persistent_page("osu_preview", None, {"width": 1280, "height": 720}) as page:
        await page.goto(f"file://{template_path}")
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_function(
            f"() => document.querySelector('{img_selector}') &&"
            f" document.querySelector('{img_selector}').src.startsWith('blob:')",
            timeout=120_000,
        )
        blob_url = await page.locator(img_selector).get_attribute("src")
        result = await page.evaluate(
            """async (url) => {
                const response = await fetch(url);
                const blob = await response.blob();
                const encoded = await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.readAsDataURL(blob);
                });
                const data = document.documentElement.dataset;
                return {
                    encoded,
                    previewStart: Number(data.previewStart),
                    previewEnd: Number(data.previewEnd),
                    actualStart: Number(data.actualStart),
                    actualEnd: Number(data.actualEnd),
                };
            }""",
            blob_url,
        )

    return RenderedPreviewChunk(
        data=base64.b64decode(result["encoded"]),
        preview_start=int(result["previewStart"]),
        preview_end=int(result["previewEnd"]),
        actual_start=int(result["actualStart"]),
        actual_end=int(result["actualEnd"]),
    )


def _skin_cache_key(assets: dict[str, str]) -> str:
    if not assets:
        return "vector"
    digest = hashlib.sha256()
    for name, source in sorted(assets.items()):
        digest.update(name.encode())
        digest.update(source.encode())
    return digest.hexdigest()[:10]


def _resolve_ffmpeg() -> str:
    configured = plugin_config.osu_preview_ffmpeg_path
    if configured is not None:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        raise RuntimeError(f"配置的 FFmpeg 不存在：{path}")
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    raise RuntimeError("生成完整预览需要 FFmpeg，请安装 FFmpeg 或配置 osu_preview_ffmpeg_path")


async def _combine_gifs(chunk_paths: list[Path], output_path: Path) -> None:
    concat_path = chunk_paths[0].parent / "concat.txt"
    concat_lines = []
    for path in chunk_paths:
        escaped_path = path.resolve().as_posix().replace("'", "'\\''")
        concat_lines.append(f"file '{escaped_path}'\n")
    concat_path.write_text("".join(concat_lines), encoding="utf-8")

    process = await asyncio.create_subprocess_exec(
        _resolve_ffmpeg(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        detail = stderr.decode(errors="replace")[-2000:]
        raise RuntimeError(f"FFmpeg 合成完整预览失败：{detail}")


# ===========================================================================
# 旧链路（fallback）：原 draw_full_osu_preview / draw_osu_preview 函数体原样保留
# ===========================================================================
async def _legacy_draw_full_osu_preview(
    beatmap_id: int,
    beatmapset_id: int,
    progress_callback: Callable[[float], Awaitable[None]] | None = None,
    target_mode: int | None = None,
) -> Path:
    osu_file, template = await load_osu_file_and_setup_template(template_path, beatmap_id, beatmapset_id)
    osu_file = _convert_preview_mode(osu_file, target_mode)
    taiko_skin_assets = {}
    mode = _preview_mode(osu_file)
    is_taiko = mode == 1
    if is_taiko:
        taiko_skin_assets = await load_taiko_skin_assets()

    cache_dir = map_path / str(beatmapset_id) / "preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if is_taiko:
        scale = _taiko_full_preview_scale()
        frame_interval = _taiko_full_preview_frame_interval()
        chunk_duration = taiko_full_preview_chunk_duration
    elif mode in {0, 2}:
        scale = _std_catch_full_preview_scale()
        frame_interval = _std_catch_full_preview_frame_interval()
        chunk_duration = taiko_full_preview_chunk_duration
    else:
        scale = _full_preview_scale()
        frame_interval = _full_preview_frame_interval()
        chunk_duration = full_preview_chunk_duration
    width = round(640 * scale)
    height = round(480 * scale)
    cache_path = (
        cache_dir
        / (
            f"{beatmap_id}-full-v{full_preview_cache_version}-"
            f"mode{mode}-{_skin_cache_key(taiko_skin_assets)}-{width}x{height}-{frame_interval}ms.mp4"
        )
    ).resolve()
    if cache_path.is_file() and cache_path.stat().st_size:
        return cache_path

    lock = _full_preview_locks.setdefault(cache_path, asyncio.Lock())
    async with lock:
        if cache_path.is_file() and cache_path.stat().st_size:
            return cache_path

        with tempfile.TemporaryDirectory(prefix=f"osubot-preview-{beatmap_id}-", dir=cache_dir) as temp_name:
            render_started_at = time.perf_counter()
            temp_dir = Path(temp_name)
            chunk_paths: list[Path] = []
            first_chunk = await _render_gif_chunk(
                osu_file,
                template,
                taiko_skin_assets,
                duration=chunk_duration,
                use_map_start=True,
                scale=scale,
                frame_time_span=frame_interval,
            )
            first_path = temp_dir / "0000.gif"
            first_path.write_bytes(first_chunk.data)
            chunk_paths.append(first_path)

            chunk_start = first_chunk.actual_end
            chunk_index = 1
            total_chunks = max(
                1,
                (first_chunk.preview_end - first_chunk.preview_start + chunk_duration - 1) // chunk_duration,
            )
            estimate_sample_chunks = min(3, total_chunks)
            estimate_sent = False
            while chunk_start < first_chunk.preview_end:
                logger.info(
                    f"正在生成谱面 <{beatmap_id}> 完整预览："
                    f"{chunk_start - first_chunk.preview_start} / "
                    f"{first_chunk.preview_end - first_chunk.preview_start} ms"
                )
                chunk = await _render_gif_chunk(
                    osu_file,
                    template,
                    taiko_skin_assets,
                    duration=chunk_duration,
                    start_time=chunk_start,
                    scale=scale,
                    frame_time_span=frame_interval,
                )
                chunk_path = temp_dir / f"{chunk_index:04d}.gif"
                chunk_path.write_bytes(chunk.data)
                chunk_paths.append(chunk_path)
                if chunk.actual_end <= chunk_start:
                    raise RuntimeError("完整预览渲染时间未向前推进")
                chunk_start = chunk.actual_end
                chunk_index += 1
                if progress_callback is not None and not estimate_sent and chunk_index >= estimate_sample_chunks:
                    elapsed = time.perf_counter() - render_started_at
                    remaining_chunks = max(total_chunks - chunk_index, 0)
                    ffmpeg_allowance = max(
                        3.0,
                        (first_chunk.preview_end - first_chunk.preview_start) / 1000 * 0.02,
                    )
                    estimated_remaining = elapsed / chunk_index * remaining_chunks + ffmpeg_allowance
                    try:
                        await progress_callback(estimated_remaining)
                    except Exception:
                        logger.exception("发送完整预览预计时间失败")
                    estimate_sent = True

            if progress_callback is not None and not estimate_sent:
                try:
                    await progress_callback(max(3.0, time.perf_counter() - render_started_at))
                except Exception:
                    logger.exception("发送完整预览预计时间失败")

            temp_output = temp_dir / "preview.mp4"
            await _combine_gifs(chunk_paths, temp_output)
            temp_output.replace(cache_path)

    return cache_path


async def _legacy_draw_osu_preview(
    beatmap_id: int,
    beatmapset_id: int,
    full: bool = False,
    target_mode: int | None = None,
) -> bytes | Path:
    if full:
        return await _legacy_draw_full_osu_preview(beatmap_id, beatmapset_id, target_mode=target_mode)

    osu_file, template = await load_osu_file_and_setup_template(template_path, beatmap_id, beatmapset_id)
    osu_file = _convert_preview_mode(osu_file, target_mode)
    taiko_skin_assets = {}
    if re.search(r"(?m)^Mode\s*:\s*1\s*$", osu_file):
        taiko_skin_assets = await load_taiko_skin_assets()
    chunk = await _render_gif_chunk(
        osu_file,
        template,
        taiko_skin_assets,
        duration=10_000,
    )
    return chunk.data


# ===========================================================================
# core 链路
# ===========================================================================
async def _core_bytes(
    bid: int,
    source_mode: int | None,
    target_mode: int | None,
    mods: Optional[Sequence[str]],
    fmt: PreviewFormat = "gif",
    time_range: Optional[str] = None,
) -> bytes:
    p = await render_with_core(
        bid,
        fmt=fmt,
        source_mode=source_mode,
        target_mode=target_mode,
        mods=mods,
        time_range=time_range,
    )
    return read_core_output(p)


async def _core_full_video(
    bid: int,
    source_mode: int | None,
    target_mode: int | None,
    mods: Optional[Sequence[str]],
) -> Path:
    return await render_with_core(
        bid,
        fmt="mp4",
        source_mode=source_mode,
        target_mode=target_mode,
        mods=mods,
    )


_RenderResult = TypeVar("_RenderResult")


async def _prefer_core(
    core: Callable[[], Awaitable[_RenderResult]],
    fallback: Callable[[], Awaitable[_RenderResult]],
    *,
    label: str,
) -> _RenderResult:
    """Apply the native-first fallback policy in one place."""
    try:
        return await core()
    except CorePreviewError as error:
        logger.warning("%s原生渲染失败，回退旧链路: %s", label, error)
        return await fallback()


def _to_bytes(result) -> bytes:
    """把 bytes / BytesIO / Path 统一成 bytes。"""
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    if isinstance(result, BytesIO):
        return result.getvalue()
    if isinstance(result, Path):
        return result.read_bytes()
    return bytes(result)


# ===========================================================================
# 对外 API（保持/扩展原签名）
# ===========================================================================
async def draw_osu_preview(
    beatmap_id: int,
    beatmapset_id: int,
    full: bool = False,
    target_mode: int | None = None,
    mods: Optional[Sequence[str]] = None,
    source_mode: int | None = None,
) -> bytes | Path:
    """Render GIF bytes or a complete MP4 with an automatic legacy fallback."""
    if full:
        return await draw_full_osu_preview(
            beatmap_id,
            beatmapset_id,
            target_mode=target_mode,
            mods=mods,
            source_mode=source_mode,
        )

    return await _prefer_core(
        lambda: _core_bytes(beatmap_id, source_mode, target_mode, mods, fmt="gif"),
        lambda: _legacy_draw_osu_preview(beatmap_id, beatmapset_id, full=False, target_mode=target_mode),
        label="GIF ",
    )


async def draw_full_osu_preview(
    beatmap_id: int,
    beatmapset_id: int,
    progress_callback: Callable[[float], Awaitable[None]] | None = None,
    target_mode: int | None = None,
    mods: Optional[Sequence[str]] = None,
    source_mode: int | None = None,
) -> Path:
    """Render a complete MP4; progress callbacks apply to the legacy fallback."""

    async def render_core() -> Path:
        if progress_callback is not None:
            try:
                await progress_callback(60.0)
            except Exception:
                logger.exception("发送原生完整预览预计时间失败")
        return await _core_full_video(beatmap_id, source_mode, target_mode, mods)

    return await _prefer_core(
        render_core,
        lambda: _legacy_draw_full_osu_preview(
            beatmap_id,
            beatmapset_id,
            progress_callback=progress_callback,
            target_mode=target_mode,
        ),
        label="完整视频 ",
    )


# ===========================================================================
# 统一入口：std / taiko / catch / mania 都走这里
# ===========================================================================
async def render_preview(
    bid: int,
    sid: int,
    mode: int,
    *,
    fmt: PreviewFormat = "png",
    mods: Optional[Sequence[str]] = None,
    time_range: Optional[str] = None,
    progress_callback: Callable[[float], Awaitable[None]] | None = None,
    source_mode: int | None = None,
    full_image: bool = False,
) -> bytes | Path:
    """统一渲染入口。

    fmt:
      "png" / "gif" -> 返回 bytes
      "mp4"         -> 返回 Path（完整视频，等价 draw_full_osu_preview）
    """
    mode = int(mode)

    if fmt == "mp4":
        return await draw_full_osu_preview(
            bid,
            sid,
            progress_callback=progress_callback,
            target_mode=mode,
            mods=mods,
            source_mode=source_mode,
        )

    async def fallback() -> bytes:
        if fmt == "gif":
            return await _legacy_draw_osu_preview(bid, sid, full=False, target_mode=mode)
        if mode == 1:
            from ..file import download_osu
            from .taiko_preview import parse_map, map_to_image

            osu = await download_osu(sid, bid)
            return _to_bytes(map_to_image(parse_map(osu)))
        if mode == 2:
            from .catch_preview import draw_cath_preview

            return _to_bytes(await draw_cath_preview(bid, sid, mods or []))
        if mode == 3:
            from ..file import download_osu
            from ..mania import generate_preview_pic

            osu = await download_osu(sid, bid)
            return _to_bytes(await generate_preview_pic(osu, full_image))
        return await _legacy_draw_osu_preview(bid, sid, full=False, target_mode=0)

    return await _prefer_core(
        lambda: _core_bytes(bid, source_mode, mode, mods, fmt=fmt, time_range=time_range),
        fallback,
        label=f"{mode=} {fmt=} ",
    )
