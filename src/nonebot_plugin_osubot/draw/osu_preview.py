import base64
from pathlib import Path

from nonebot_plugin_htmlrender import get_new_page

from .utils import load_osu_file_and_setup_template

template_path = str(Path(__file__).parent / "osu_preview_templates")


async def draw_osu_preview(beatmap_id, beatmapset_id) -> bytes:
    osu_file, template = await load_osu_file_and_setup_template(template_path, beatmap_id, beatmapset_id)
    img_selector = "img"
    base_url = Path(template_path).as_uri() + "/"
    worker_script_path = Path(template_path) / "gif.js" / "gif.worker.js"

    # 读取 worker 脚本内容
    with open(worker_script_path, encoding="utf-8") as f:
        worker_script_content = f.read()
    worker_base64 = base64.b64encode(worker_script_content.encode("utf-8")).decode("utf-8")
    worker_data_uri = f"data:application/javascript;base64,{worker_base64}"
    async with get_new_page(2) as page:
        await page.goto(f"file://{template_path}")
        await page.set_content(
            await template.render_async(osu_file=osu_file, base_url=base_url, worker_data_uri=worker_data_uri),
            wait_until="networkidle",
        )
        await page.wait_for_function(
            f"() => document.querySelector('{img_selector}') &&"
            f" document.querySelector('{img_selector}').src.startsWith('blob:')",
            timeout=60000,
        )
        blob_url = await page.locator(img_selector).get_attribute("src")
        base64_data = await page.evaluate(
            """async (url) => {
                    const response = await fetch(url);
                    const blob = await response.blob();

                    return new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onloadend = () => {
                            resolve(reader.result.split(',')[1]);
                        };
                        reader.readAsDataURL(blob);
                    });
                }""",
            blob_url,
        )
    gif_bytes = base64.b64decode(base64_data)
    return gif_bytes
