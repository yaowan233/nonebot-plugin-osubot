from playwright.async_api import ViewportSize
from nonebot_plugin_htmlrender import get_new_page


async def draw_match_history(match_id: str) -> bytes:
    async with get_new_page(
        viewport=ViewportSize(width=900, height=1), extra_http_headers={"Accept-Language": "zh-CN"}
    ) as page:
        await page.goto(f"https://osu.ppy.sh/community/matches/{match_id}", wait_until="networkidle")
        await page.add_style_tag(
            content="""
            .mp-history-event, .mp-history-content__item--event, .nav2, .audio-player {
                display: none !important;
            }
        """
        )
        while True:
            try:
                await page.wait_for_selector(".show-more-link", timeout=3000)
                await page.evaluate("document.querySelector('.show-more-link').click()")
            except Exception:
                break
        pic = await page.screenshot(omit_background=True, full_page=True, quality=60, type="jpeg")
        return pic
