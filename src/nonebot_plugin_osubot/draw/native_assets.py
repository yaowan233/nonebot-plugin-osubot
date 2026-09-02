"""Image localization helpers for native SVG renderers."""

from __future__ import annotations

import re
import time
import base64
import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image

from ..file import get_projectimg


_REMOTE_CACHE = Path("data") / "osu" / "native-assets"
_REMOTE_CACHE_TTL = 7 * 24 * 3600
_remote_locks: dict[Path, asyncio.Lock] = {}


def _local_path(source: str) -> Path | None:
    try:
        if source.startswith("file:"):
            raw_path = unquote(urlparse(source).path)
            if re.match(r"^/[A-Za-z]:/", raw_path):
                raw_path = raw_path[1:]
            path = Path(raw_path)
        elif "://" not in source:
            path = Path(source)
        else:
            return None
        return path if path.is_file() else None
    except (OSError, ValueError):
        return None


def _data_uri_bytes(source: str) -> bytes | None:
    try:
        header, encoded = source.split(",", 1)
        if ";base64" in header:
            return base64.b64decode(encoded)
    except (ValueError, TypeError):
        pass
    return None


def _normalized_data_uri(data: bytes, max_size: tuple[int, int], image_format: str) -> str:
    output = BytesIO()
    with Image.open(BytesIO(data)) as source:
        source.seek(0)
        frame = source.convert("RGBA" if image_format == "PNG" else "RGB")
        frame.thumbnail(max_size, Image.Resampling.LANCZOS)
        try:
            options = {"quality": 86} if image_format == "JPEG" else {}
            frame.save(output, image_format, **options)
        finally:
            frame.close()
    mime = "jpeg" if image_format == "JPEG" else "png"
    return f"data:image/{mime};base64,{base64.b64encode(output.getvalue()).decode()}"


async def _remote_image_bytes(source: str) -> bytes:
    digest = hashlib.sha256(source.encode()).hexdigest()
    cache_path = _REMOTE_CACHE / f"{digest}.img"
    try:
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime < _REMOTE_CACHE_TTL:
            return await asyncio.to_thread(cache_path.read_bytes)
    except OSError:
        pass
    lock = _remote_locks.setdefault(cache_path, asyncio.Lock())
    async with lock:
        try:
            if cache_path.exists() and time.time() - cache_path.stat().st_mtime < _REMOTE_CACHE_TTL:
                return await asyncio.to_thread(cache_path.read_bytes)
        except OSError:
            pass
        remote = await get_projectimg(source)
        data = remote.getvalue()
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_name(f".{cache_path.name}.{id(asyncio.current_task())}.tmp")
            try:
                await asyncio.to_thread(temporary.write_bytes, data)
                temporary.replace(cache_path)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return data


async def image_source_data_uri(
    source: str | None,
    *,
    max_size: tuple[int, int],
    image_format: str = "PNG",
) -> str | None:
    """Load a data/file/http image and normalize it for resvg embedding."""

    if not source:
        return None
    source = str(source)
    data = _data_uri_bytes(source) if source.startswith("data:") else None
    if data is None:
        local_path = _local_path(source)
        try:
            if local_path is not None:
                data = await asyncio.to_thread(local_path.read_bytes)
            elif source.startswith(("http://", "https://")):
                data = await _remote_image_bytes(source)
            else:
                return None
        except Exception:
            return None
    try:
        return await asyncio.to_thread(_normalized_data_uri, data, max_size, image_format.upper())
    except Exception:
        return None
