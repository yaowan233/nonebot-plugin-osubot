from pathlib import Path

from nonebot_plugin_htmlrender import get_new_page

from .utils import load_osu_file_and_setup_template

template_path = str(Path(__file__).parent / "catch_preview_templates")


async def draw_cath_preview(beatmap_id, beatmapset_id, mods) -> bytes:
    osu_file, template = await load_osu_file_and_setup_template(template_path, beatmap_id, beatmapset_id)
    is_hr = 1 if "HR" in mods else 0
    is_ez = 1 if "EZ" in mods else 0
    is_dt = 1 if "DT" in mods else 0
    is_ht = 1 if "HT" in mods else 0
    async with get_new_page(2) as page:
        await page.goto(f"file://{template_path}")
        await page.set_content(
            await template.render_async(
                beatmap_id=beatmap_id, osu_file=osu_file, is_hr=is_hr, is_ez=is_ez, is_dt=is_dt, is_ht=is_ht
            ),
            wait_until="networkidle",
        )
        return await page.screenshot(full_page=True, type="jpeg", quality=60, omit_background=True)
