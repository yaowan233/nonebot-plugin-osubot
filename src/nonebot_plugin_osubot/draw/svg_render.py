"""Fast native SVG rasterization helpers for fixed-layout image cards."""

import asyncio
import base64
import html
import mimetypes
import threading
import xml.etree.ElementTree as ElementTree
from io import BytesIO
from pathlib import Path
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from resvg_py import svg_to_bytes


FONT_PATH = Path(__file__).parent.parent / "osufile" / "fonts" / "Torus Regular.otf"
LATIN_FONT_PATH = Path(__file__).parent / "template_assets" / "torus-regular.woff"
EXTRA_FONT_PATH = Path(__file__).parent / "template_assets" / "extra.woff"
FONT_FAMILY = "Source Han Sans SC"
_thumbnail_locks: dict[Path, threading.Lock] = {}
_thumbnail_locks_guard = threading.Lock()
_NATIVE_RENDER_FONT_SIZES = (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25, 28, 31, 34, 35, 43)


def escape_text(value: object) -> str:
    return html.escape(str(value), quote=True)


@lru_cache(maxsize=128)
def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def font_for_text(value: object, size: int, font_kind: str | None = None) -> ImageFont.FreeTypeFont:
    if font_kind == "extra":
        path = EXTRA_FONT_PATH
    else:
        path = LATIN_FONT_PATH if str(value).isascii() else FONT_PATH
    return _font(path, size)


def fit_text(value: object, max_width: int, start_size: int, min_size: int) -> int:
    """Return the largest font size that fits a fixed SVG text slot."""
    text = str(value)
    font = font_for_text(text, start_size)
    width = font.getlength(text)
    if width <= max_width:
        return start_size
    # Font metrics scale linearly. Start at the projected size and only correct
    # rounding instead of opening the (large CJK) font once for every size.
    size = max(min_size, min(start_size, int(start_size * max_width / width)))
    while size > min_size and font_for_text(text, size).getlength(text) > max_width:
        size -= 1
    return size


def text_width(value: object, size: int) -> float:
    return font_for_text(value, size).getlength(str(value))


def truncate_text(value: object, max_width: float, size: int) -> str:
    """Truncate a single line using the exact font metrics used by the renderer."""
    text = str(value)
    if text_width(text, size) <= max_width:
        return text
    suffix = "…"
    available = max(0, max_width - text_width(suffix, size))
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if text_width(text[:middle], size) <= available:
            low = middle
        else:
            high = middle - 1
    return text[:low] + suffix


@lru_cache(maxsize=512)
def file_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


@lru_cache(maxsize=512)
def _thumbnail_data_uri(
    path: Path,
    modified_ns: int,
    file_size: int,
    max_width: int,
    max_height: int,
    quality: int,
) -> str:
    del modified_ns, file_size  # They invalidate cached thumbnails when a source revision changes.
    cache_path = path.with_name(f"{path.stem}.card-{max_width}x{max_height}-q{quality}.jpg")
    with _thumbnail_locks_guard:
        cache_lock = _thumbnail_locks.setdefault(cache_path, threading.Lock())
    with cache_lock:
        if not cache_path.exists() or cache_path.stat().st_mtime_ns < path.stat().st_mtime_ns:
            temporary = cache_path.with_name(f".{cache_path.name}.{threading.get_ident()}.tmp")
            try:
                with Image.open(path) as source:
                    source.draft("RGB", (max_width, max_height))
                    thumbnail = ImageOps.fit(
                        source.convert("RGB"),
                        (max_width, max_height),
                        method=Image.Resampling.LANCZOS,
                    )
                    thumbnail.save(temporary, "JPEG", quality=quality)
                    thumbnail.close()
                temporary.replace(cache_path)
            finally:
                temporary.unlink(missing_ok=True)
        encoded = base64.b64encode(cache_path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def thumbnail_data_uri(
    path: Path,
    *,
    max_width: int = 512,
    max_height: int = 256,
    quality: int = 84,
) -> str:
    """Return a source-revision-aware card thumbnail without caching final cards."""
    stat = path.stat()
    return _thumbnail_data_uri(path.resolve(), stat.st_mtime_ns, stat.st_size, max_width, max_height, quality)


def render_svg_jpeg(
    svg: str,
    *,
    width: int,
    height: int,
    quality: int = 92,
    image_rendering: str = "optimize_quality",
    background_data_uri: str | None = None,
) -> BytesIO:
    """Rasterize SVG geometry, then composite cached-font text and encode JPEG."""
    root = ElementTree.fromstring(svg)
    text_specs: list[tuple[float, float, str, int, str, str, float, str | None, str | None, str | None]] = []
    for parent in root.iter():
        for child in list(parent):
            if child.tag.rsplit("}", 1)[-1] != "text":
                continue
            text_specs.append(
                (
                    float(child.attrib.get("x", 0)),
                    float(child.attrib.get("y", 0)),
                    "".join(child.itertext()),
                    round(float(child.attrib.get("font-size", 16))),
                    child.attrib.get("fill", "#000000"),
                    child.attrib.get("text-anchor", "start"),
                    float(child.attrib.get("opacity", 1)),
                    child.attrib.get("data-gradient-start"),
                    child.attrib.get("data-gradient-end"),
                    child.attrib.get("data-font"),
                )
            )
            parent.remove(child)
    geometry_svg = ElementTree.tostring(root, encoding="unicode")
    png = svg_to_bytes(
        svg_string=geometry_svg,
        width=width,
        height=height,
        skip_system_fonts=True,
        image_rendering=image_rendering,
    )
    result = BytesIO()
    with Image.open(BytesIO(png)) as image:
        geometry = image.convert("RGBA")
    if background_data_uri:
        with Image.open(BytesIO(_fitted_background_jpeg(background_data_uri, width, height))) as background:
            composed = background.convert("RGBA")
        composed.alpha_composite(geometry)
        geometry.close()
    else:
        composed = geometry
    draw = ImageDraw.Draw(composed)
    anchors = {"start": "ls", "middle": "ms", "end": "rs"}
    for x, y, value, size, fill, text_anchor, opacity, gradient_start, gradient_end, font_kind in text_specs:
        anchor = anchors.get(text_anchor, "ls")
        font = font_for_text(value, size, font_kind)
        if gradient_start and gradient_end:
            mask = Image.new("L", composed.size, 0)
            ImageDraw.Draw(mask).text(
                (x, y),
                value,
                font=font,
                fill=round(255 * opacity),
                anchor=anchor,
            )
            if bounds := mask.getbbox():
                start = ImageColor.getrgb(gradient_start)
                end = ImageColor.getrgb(gradient_end)
                gradient = Image.new("RGB", (1, bounds[3] - bounds[1]))
                gradient.putdata(
                    [
                        tuple(
                            round(first + (last - first) * row / max(1, bounds[3] - bounds[1] - 1))
                            for first, last in zip(start, end)
                        )
                        for row in range(bounds[3] - bounds[1])
                    ]
                )
                gradient = gradient.resize((bounds[2] - bounds[0], bounds[3] - bounds[1]))
                composed.paste(gradient, bounds[:2], mask.crop(bounds))
                gradient.close()
            mask.close()
            continue
        red, green, blue, alpha = ImageColor.getcolor(fill, "RGBA")
        draw.text(
            (x, y),
            value,
            font=font,
            fill=(red, green, blue, round(alpha * opacity)),
            anchor=anchor,
        )
    composed.convert("RGB").save(result, "JPEG", quality=quality)
    composed.close()
    result.seek(0)
    return result


async def render_svg_jpeg_async(
    svg: str,
    *,
    width: int,
    height: int,
    quality: int = 92,
    image_rendering: str = "optimize_quality",
    background_data_uri: str | None = None,
) -> BytesIO:
    """Keep native rasterization and JPEG encoding away from the bot event loop."""
    return await asyncio.to_thread(
        render_svg_jpeg,
        svg,
        width=width,
        height=height,
        quality=quality,
        image_rendering=image_rendering,
        background_data_uri=background_data_uri,
    )


@lru_cache(maxsize=32)
def _fitted_background_jpeg(data_uri: str, width: int, height: int) -> bytes:
    """Cache the full-canvas cover resize outside the SVG rasterizer."""
    encoded = data_uri.split(",", 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as source:
        fitted = ImageOps.fit(
            source.convert("RGB"),
            (width, height),
            method=Image.Resampling.BILINEAR,
        )
    output = BytesIO()
    try:
        fitted.save(output, "JPEG", quality=90)
    finally:
        fitted.close()
    return output.getvalue()


def render_svg_png(svg: str, *, width: int, height: int) -> bytes:
    """Rasterize an SVG shape/image layer without loading any fonts."""
    return svg_to_bytes(
        svg_string=svg,
        width=width,
        height=height,
        skip_system_fonts=True,
        image_rendering="optimize_quality",
    )


def _warm_up_native_renderer_sync() -> None:
    """Load common card fonts and initialize resvg before the first command."""
    for size in _NATIVE_RENDER_FONT_SIZES:
        font_for_text("OSU 0123456789", size)
        font_for_text("谱面成绩", size)
    font_for_text("\ue800", 25, "extra")
    render_svg_png(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        '<rect width="16" height="16" fill="#101824"/>'
        "</svg>",
        width=16,
        height=16,
    )


async def warm_up_native_renderer() -> None:
    """Warm the native card renderer without blocking plugin startup."""
    await asyncio.to_thread(_warm_up_native_renderer_sync)
