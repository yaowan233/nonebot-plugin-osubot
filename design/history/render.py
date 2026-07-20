import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


ROOT = Path(__file__).parent


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=1)
        await page.goto((ROOT / "concepts.html").as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        for name in ("editorial", "console", "timeline"):
            await page.locator(f"#history-{name}").screenshot(path=ROOT / f"history-{name}.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
