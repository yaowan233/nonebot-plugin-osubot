from pathlib import Path

import jinja2
from nonebot_plugin_htmlrender import get_new_page

template_path = str(Path(__file__).parent / "catch_preview_templates")


async def draw_cath_preview(beatmap_id) -> bytes:
    template_name = "pic.html"
    template_env = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(template_path),
        enable_async=True,
    )
    template = template_env.get_template(template_name)
    async with get_new_page(2) as page:
        await page.goto(f"file://{template_path}")
        await page.set_content(await template.render_async(beatmap_id=beatmap_id), wait_until="networkidle")
        return await page.screenshot(full_page=True, type="png", omit_background=True)
