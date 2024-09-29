from pathlib import Path

import jinja2
from nonebot_plugin_htmlrender import get_new_page

from ..file import map_path, download_osu

template_path = str(Path(__file__).parent / "catch_preview_templates")


async def draw_cath_preview(beatmap_id, beatmapset_id) -> bytes:
    path = map_path / str(beatmapset_id)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    osu = path / f"{beatmap_id}.osu"
    if not osu.exists():
        await download_osu(beatmapset_id, beatmap_id)
    with open(osu, encoding="utf-8") as f:
        osu_file = f.read()
    template_name = "pic.html"
    template_env = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(template_path),
        enable_async=True,
    )
    template = template_env.get_template(template_name)
    async with get_new_page(2) as page:
        await page.goto(f"file://{template_path}")
        await page.set_content(
            await template.render_async(beatmap_id=beatmap_id, osu_file=osu_file), wait_until="networkidle"
        )
        return await page.screenshot(full_page=True, type="jpeg", quality=60, omit_background=True)
