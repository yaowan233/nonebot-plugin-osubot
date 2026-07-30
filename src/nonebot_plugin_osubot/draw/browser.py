"""跨模板复用的 playwright 持久页面池。

每个模板一个持久 page：避免每次出图都新建 context/page（约 0.3s），
goto 模板文件也只需在页面创建时执行一次（建立 file:// 源，
让字体等相对路径资源以模板目录为基准）。
"""

import asyncio
from contextlib import asynccontextmanager

from nonebot_plugin_htmlrender import get_render

_pages = {}  # key -> page
_contexts = {}  # key -> context
_locks = {}  # key -> asyncio.Lock


async def _create_page(key, goto_uri, viewport, device_scale_factor):
    session = await get_render()
    context = await session.handle.new_context(viewport=viewport, device_scale_factor=device_scale_factor)
    page = await context.new_page()
    if goto_uri:
        await page.goto(goto_uri, wait_until="load")
    _contexts[key] = context
    _pages[key] = page
    return page


async def _drop_page(key):
    context = _contexts.pop(key, None)
    page = _pages.pop(key, None)
    try:
        if context is not None:
            await context.close()
        elif page is not None:
            await page.close()
    except Exception:
        pass


@asynccontextmanager
async def persistent_page(key: str, goto_uri: str | None, viewport: dict, device_scale_factor: float = 2):
    """获取某个模板的持久页面；同一模板并发渲染会串行，页面异常时自动丢弃下次重建。"""
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        page = _pages.get(key)
        if page is None or page.is_closed():
            await _drop_page(key)
            page = await _create_page(key, goto_uri, viewport, device_scale_factor)
        else:
            # viewport 可能随调用变化（如 bmap 高度自适应），重设成本可忽略
            await page.set_viewport_size(viewport)
        try:
            yield page
        except Exception:
            await _drop_page(key)
            raise
