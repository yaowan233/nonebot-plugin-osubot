import asyncio
import base64
import json
import threading
from io import BytesIO
from pathlib import Path
from functools import lru_cache
from typing import Any

import jinja2
from PIL import Image, ImageOps

from ..info import get_bg
from ..file import get_projectimg, map_path, user_cache_path
from .browser import persistent_page, wait_for_page_assets


ASSET_PATH = Path(__file__).parent / "template_assets"
BACKGROUND_SIZE = (1400, 900)
_background_locks: dict[Path, asyncio.Lock] = {}


def duration_text(seconds: float) -> str:
    seconds = round(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


@lru_cache(maxsize=512)
def _file_data_uri(path: Path, mime: str, modified_ns: int, file_size: int) -> str:
    del modified_ns, file_size
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def file_data_uri(path: Path, mime: str) -> str:
    stat = path.stat()
    return _file_data_uri(path.resolve(), mime, stat.st_mtime_ns, stat.st_size)


def _source_to_jpeg_data_uri(source: BytesIO) -> str:
    source.seek(0)
    with Image.open(source) as image:
        output = BytesIO()
        image.convert("RGB").save(output, "JPEG", quality=88)
    return f"data:image/jpeg;base64,{base64.b64encode(output.getvalue()).decode()}"


async def remote_image_data_uri(url: str) -> str:
    source = await get_projectimg(url)
    return await asyncio.to_thread(_source_to_jpeg_data_uri, source)


async def cached_avatar_data_uri(user_id: int) -> str:
    """Cache mapper avatars independently from the page renderer."""
    cache_path = user_cache_path / str(user_id) / "mapper_avatar.jpg"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        return file_data_uri(cache_path, "image/jpeg")
    result = await remote_image_data_uri(f"https://a.ppy.sh/{user_id}")
    try:
        _header, encoded = result.split(",", 1)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_bytes(base64.b64decode(encoded))
        temporary.replace(cache_path)
    except Exception:
        return result
    return result


def image_data_uri(image: Image.Image) -> str:
    output = BytesIO()
    rgb_image = image.convert("RGB")
    try:
        rgb_image.save(output, "JPEG", quality=90, optimize=True)
    finally:
        rgb_image.close()
    return f"data:image/jpeg;base64,{base64.b64encode(output.getvalue()).decode()}"


def _background_cache_current(cache_path: Path, osu_path: Path) -> bool:
    return cache_path.exists() and (
        not osu_path.exists() or cache_path.stat().st_mtime_ns >= osu_path.stat().st_mtime_ns
    )


def _save_background_cache(image: Image.Image, cache_path: Path) -> None:
    temporary = cache_path.with_name(f".{cache_path.name}.{threading.get_ident()}.tmp")
    try:
        rendered = ImageOps.fit(image.convert("RGB"), BACKGROUND_SIZE, method=Image.Resampling.LANCZOS)
        try:
            rendered.save(temporary, "JPEG", quality=86)
        finally:
            rendered.close()
        temporary.replace(cache_path)
    finally:
        temporary.unlink(missing_ok=True)


async def beatmap_background_data_uri(map_id: int, set_id: int, fallback_url: str) -> str:
    set_path = map_path / str(set_id)
    cache_path = set_path / f"{map_id}.render-background.jpg"
    osu_path = set_path / f"{map_id}.osu"
    if _background_cache_current(cache_path, osu_path):
        return file_data_uri(cache_path, "image/jpeg")
    lock = _background_locks.setdefault(cache_path, asyncio.Lock())
    async with lock:
        if _background_cache_current(cache_path, osu_path):
            return file_data_uri(cache_path, "image/jpeg")
        set_path.mkdir(parents=True, exist_ok=True)
        try:
            image = await get_bg(map_id, set_id)
            try:
                await asyncio.to_thread(_save_background_cache, image, cache_path)
            finally:
                image.close()
        except Exception:
            result = await remote_image_data_uri(fallback_url)
            if not result.startswith("data:"):
                return result
            temporary = cache_path.with_name(f".{cache_path.name}.{id(asyncio.current_task())}.tmp")
            try:
                temporary.write_bytes(base64.b64decode(result.split(",", 1)[1]))
                temporary.replace(cache_path)
            finally:
                temporary.unlink(missing_ok=True)
        return file_data_uri(cache_path, "image/jpeg")


async def render_map_template(
    template_path: Path,
    payload: dict[str, Any],
    element_id: str,
    viewport_height: int,
) -> BytesIO:
    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_path), autoescape=True)  # noqa: S701
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = template_env.get_template("index.html").render(
        payload_json=payload_json,
        extra_font_url=file_data_uri(ASSET_PATH / "extra.woff", "font/woff"),
        torus_regular_url=file_data_uri(ASSET_PATH / "torus-regular.woff", "font/woff"),
        torus_semibold_url=file_data_uri(ASSET_PATH / "torus-semibold.woff", "font/woff"),
    )
    async with persistent_page("map_render", None, {"width": 1500, "height": viewport_height}) as page:
        await page.set_content(html, wait_until="domcontentloaded")
        await wait_for_page_assets(page)
        element = page.locator(f"#{element_id}")
        return BytesIO(await element.screenshot(type="jpeg", quality=92))
