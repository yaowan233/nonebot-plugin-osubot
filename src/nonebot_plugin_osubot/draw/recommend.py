from pathlib import Path

import jinja2

from ..schema.alphaosu import RecommendData
from .browser import persistent_page

template_path = Path(__file__).parent / "templates"


async def draw_recommend(data: RecommendData, username: str, avatar_url: str) -> bytes:
    template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(str(template_path)), enable_async=True
    ).get_template("recommend.html")
    async with persistent_page(
        "recommend", (template_path / "recommend.html").as_uri(), {"width": 900, "height": 600}
    ) as page:
        await page.set_content(
            await template.render_async(
                player_id=data.player_id,
                mode=data.mode,
                username=username,
                avatar_url=avatar_url,
                recommendations=[item.model_dump() for item in data.recommendations] if data.recommendations else [],
            ),
            wait_until="domcontentloaded",
        )
        await page.evaluate(
            "Promise.race([Promise.all([document.fonts.ready,"
            "...Array.from(document.images,x=>x.decode().catch(()=>{}))]),"
            "new Promise(resolve=>setTimeout(resolve,8000))])"
        )
        body = await page.query_selector("body")
        assert body
        return await body.screenshot(type="jpeg", quality=60)
