import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import jinja2
from nonebot_plugin_htmlrender import get_new_page
from PIL import Image

from ..file import get_projectimg


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
    async with get_new_page(2) as page:
        await page.set_viewport_size({"width": 1500, "height": viewport_height})
        await page.set_content(html, wait_until="networkidle")
        await page.evaluate(
            "Promise.all([document.fonts.ready,...Array.from(document.images,x=>x.decode().catch(()=>{}))])"
        )
        element = page.locator(f"#{element_id}")
        return BytesIO(await element.screenshot(type="jpeg", quality=92))
