from nonebot_plugin_htmlrender import get_new_page
from playwright.async_api import ViewportSize


async def draw_match_history(match_id: str) -> bytes:
    async with get_new_page(viewport=ViewportSize(width=800, height=1)) as page:
        await page.goto(f"https://osu.ppy.sh/community/matches/{match_id}", wait_until="networkidle")
        pic = await page.screenshot(omit_background=True, full_page=True, quality=60, type="jpeg")
        return pic
