"""成就列表渲染（Jinja2 + Playwright，网格布局，风格与 friend 一致）。

用于 /ma（已获得成就）与 /ar（成就推荐）的图片输出。
"""

from pathlib import Path

import jinja2
from typing_extensions import TypedDict

from .browser import persistent_page


class AchievementRenderRow(TypedDict):
    name: str
    icon: str
    grouping: str
    achieved_at: str


class AchievementRenderData(TypedDict):
    me_name: str
    me_avatar: str
    title: str
    subtitle: str
    total: int
    start: int
    end: int
    achievements: list[AchievementRenderRow]


async def draw_achievements(data: AchievementRenderData) -> bytes:
    """渲染成就网格图片。

    Parameters
    ----------
    data : dict
        包含 me_name / me_avatar / title / subtitle / total /
        achievements: list[dict]，每项含 name / icon / grouping / achieved_at(可选)
    """
    template_path = Path(__file__).parent / "medal_templates"
    template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(str(template_path)), enable_async=True
    ).get_template("index.html")
    async with persistent_page(
        "medal", (template_path / "index.html").as_uri(), {"width": 1280, "height": 900}
    ) as page:
        await page.set_content(await template.render_async(**data), wait_until="domcontentloaded")
        await page.evaluate(
            "Promise.race([Promise.all([document.fonts.ready,"
            "...Array.from(document.images,x=>x.decode().catch(()=>{}))]),"
            "new Promise(resolve=>setTimeout(resolve,8000))])"
        )
        element = await page.query_selector(".card")
        assert element
        return await element.screenshot(type="png")
