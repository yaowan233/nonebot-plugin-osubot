from pathlib import Path

import jinja2

from ..schema.alphaosu import RecommendData
from .browser import persistent_page, wait_for_page_assets

template_path = Path(__file__).parent / "templates"

SECTION_TITLES = {
    "overall": "综合推荐",
    "hard": "进阶推荐",
    "medium": "稳健推荐",
    "easy": "基础推荐",
}

SIDE_SECTION_ORDER = {"easy": 0, "medium": 1, "hard": 2}


async def draw_recommend(data: RecommendData, username: str, avatar_url: str) -> bytes:
    sections = [
        {
            "key": section.key,
            "title": SECTION_TITLES.get(section.key, section.title),
            "items": [item.model_dump() for item in section.items],
        }
        for section in data.sections or []
    ]
    overall_section = next((section for section in sections if section["key"] == "overall"), None)
    side_sections = sorted(
        [section for section in sections if section["key"] != "overall" and section["items"]],
        key=lambda section: SIDE_SECTION_ORDER.get(section["key"], 99),
    )
    template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(str(template_path)), enable_async=True
    ).get_template("recommend.html")
    async with persistent_page(
        "recommend", (template_path / "recommend.html").as_uri(), {"width": 1080, "height": 600}
    ) as page:
        await page.set_content(
            await template.render_async(
                player_id=data.player_id,
                mode=data.mode,
                username=username,
                avatar_url=avatar_url,
                total_count=sum(len(section.items) for section in data.sections or [])
                if data.sections
                else len(data.recommendations or []),
                recommendations=[item.model_dump() for item in data.recommendations] if data.recommendations else [],
                sections=sections,
                overall_section=overall_section,
                side_sections=side_sections,
            ),
            wait_until="domcontentloaded",
        )
        await wait_for_page_assets(page)
        body = await page.query_selector("body")
        assert body
        return await body.screenshot(type="jpeg", quality=60)
