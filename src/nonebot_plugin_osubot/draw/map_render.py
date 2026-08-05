import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import jinja2
from PIL import Image

from ..info import get_bg
from ..file import get_projectimg
from .browser import persistent_page, wait_for_page_assets


ASSET_PATH = Path(__file__).parent / "template_assets"


def duration_text(seconds: float) -> str:
    seconds = round(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def file_data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


async def remote_image_data_uri(url: str) -> str:
    source = await get_projectimg(url)
    source.seek(0)
    with Image.open(source) as image:
        image = image.convert("RGB")
        output = BytesIO()
        image.save(output, "JPEG", quality=90, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(output.getvalue()).decode()}"


def image_data_uri(image: Image.Image) -> str:
    output = BytesIO()
    rgb_image = image.convert("RGB")
    try:
        rgb_image.save(output, "JPEG", quality=90, optimize=True)
    finally:
        rgb_image.close()
    return f"data:image/jpeg;base64,{base64.b64encode(output.getvalue()).decode()}"


async def beatmap_background_data_uri(map_id: int, set_id: int, fallback_url: str) -> str:
    try:
        image = await get_bg(map_id, set_id)
        try:
            return image_data_uri(image)
        finally:
            image.close()
    except Exception:
        return await remote_image_data_uri(fallback_url)


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
