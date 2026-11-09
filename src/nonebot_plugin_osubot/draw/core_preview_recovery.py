"""Recover native .osu downloads using the plugin's mirror downloader."""

from osu_beatmap_preview import generate_preview_async

from .. import file
from .core_preview_settings import native_render_config


async def recover_preview_download(beatmap_id: int | str, options: dict) -> dict:
    source = await file.download_osu("native-preview", beatmap_id)
    if not source.read_bytes().lstrip(b"\xef\xbb\xbf\r\n ").startswith(b"osu file format"):
        raise ValueError("下载结果不是有效的 osu 谱面文件")
    return await generate_preview_async(
        beatmap_id, **{"config": native_render_config(), **options, "osu_file": source.resolve()}
    )
