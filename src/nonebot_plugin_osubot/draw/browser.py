"""HTMLRender 0.8 Playwright lease 上的持久页面池。"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from nonebot.log import logger
from nonebot_plugin_htmlrender import get_default_application

_pages: dict[str, "_PersistentPage"] = {}
_locks: dict[str, asyncio.Lock] = {}
_closing = False

_WAIT_FOR_ASSETS_SCRIPT = """
async timeoutMs => {
    const resources = [
        document.fonts.ready,
        ...Array.from(document.images, image => image.decode().catch(() => {})),
    ];
    await Promise.race([
        Promise.all(resources),
        new Promise(resolve => setTimeout(resolve, timeoutMs)),
    ]);
}
"""


@dataclass(slots=True)
class _PersistentPage:
    lease: Any
    page: Any
    goto_uri: str | None
    viewport: dict
    device_scale_factor: float


async def _drop_page(key: str) -> None:
    entry = _pages.pop(key, None)
    if entry is None:
        return
    await entry.lease.__aexit__(None, None, None)


async def _create_page(
    key: str,
    goto_uri: str | None,
    viewport: dict,
    device_scale_factor: float,
):
    app = get_default_application()
    lease = app.extensions.playwright.page(
        viewport=viewport,
        device_scale_factor=device_scale_factor,
    )
    try:
        page = await lease.__aenter__()
    except BaseException:
        # __aenter__ 失败时 context manager 尚未进入，不能调用 __aexit__。
        # 否则 asynccontextmanager 会收到 athrow，并可能再次 yield，最终掩盖
        # 原始 ProviderLifecycleError 为 "generator didn't stop after athrow()"。
        raise
    try:
        if goto_uri:
            # 持久页导航主要用于建立 file:// 基准地址。等待完整 load 会被
            # 模板中的远程头像、封面等资源拖住；具体渲染函数会自行等待
            # 必需资源，并设置更短的超时兜底。
            await page.goto(goto_uri, wait_until="domcontentloaded")
    except BaseException:
        await lease.__aexit__(None, None, None)
        raise
    _pages[key] = _PersistentPage(lease, page, goto_uri, viewport.copy(), device_scale_factor)
    return page


@asynccontextmanager
async def persistent_page(
    key: str,
    goto_uri: str | None,
    viewport: dict,
    device_scale_factor: float = 2,
):
    """复用模板页面；同一模板串行渲染，异常或参数变化时自动重建。"""
    if _closing:
        raise RuntimeError("Playwright 持久页面池正在关闭")
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        entry = _pages.get(key)
        if entry is not None and (
            entry.page.is_closed() or entry.goto_uri != goto_uri or entry.device_scale_factor != device_scale_factor
        ):
            await _drop_page(key)
            entry = None
        if entry is None:
            page = await _create_page(key, goto_uri, viewport, device_scale_factor)
        else:
            page = entry.page
        try:
            if entry is not None:
                # set_content 使用 document.write，不会创建新的 Window。
                # 模板中的顶层 const/let 会残留到下一次渲染，重复声明后
                # 整段脚本停止执行；reload 用来重建 JavaScript 执行环境。
                await page.reload(wait_until="domcontentloaded")
                if entry.viewport != viewport:
                    await page.set_viewport_size(viewport)
                    entry.viewport = viewport.copy()
            yield page
        except BaseException:
            await _drop_page(key)
            raise


async def wait_for_page_assets(page: Any, timeout_ms: int = 8000) -> None:
    """等待字体和图片，但不让不可达的远程资源阻塞截图。"""
    await page.evaluate(_WAIT_FOR_ASSETS_SCRIPT, timeout_ms)


async def close_persistent_pages() -> None:
    """在 HTMLRender Application 关闭前释放所有长期持有的页面 lease。"""
    global _closing
    _closing = True
    for key in list(_pages):
        lock = _locks.setdefault(key, asyncio.Lock())
        async with lock:
            try:
                await _drop_page(key)
            except Exception:
                logger.exception(f"关闭 Playwright 持久页面失败: {key}")
