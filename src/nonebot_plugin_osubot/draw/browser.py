"""HTMLRender 0.8 Playwright lease 上的持久页面池。"""

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from nonebot import get_plugin_config
from nonebot.log import logger
from nonebot_plugin_htmlrender import get_default_application

from ..config import Config

_pages: dict[str, "_PersistentPage"] = {}
_locks: dict[str, asyncio.Lock] = {}
_closing = False
plugin_config = get_plugin_config(Config)

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


class RenderQueueFull(RuntimeError):
    pass


class RenderQueueTimeout(TimeoutError):
    pass


class RenderTimeout(TimeoutError):
    pass


@dataclass(frozen=True, slots=True)
class RenderSchedulerSnapshot:
    queued: int
    in_flight: int
    completed: int
    failed: int
    timed_out: int
    rejected: int
    average_queue_wait: float
    average_render_time: float


class _RenderScheduler:
    """Bound admission, per-template serialisation, and render lifetime."""

    def __init__(
        self,
        *,
        max_concurrency: int,
        queue_size: int,
        queue_timeout: float,
        render_timeout: float,
    ):
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._queue_size = max(1, queue_size)
        self._queue_timeout = max(0.01, queue_timeout)
        self._render_timeout = max(0.01, render_timeout)
        self._queued = 0
        self._in_flight = 0
        self._completed = 0
        self._failed = 0
        self._timed_out = 0
        self._rejected = 0
        self._started = 0
        self._total_queue_wait = 0.0
        self._total_render_time = 0.0

    @asynccontextmanager
    async def slot(self, key: str):
        if self._queued >= self._queue_size:
            self._rejected += 1
            raise RenderQueueFull("绘图请求过多，请稍后再试")

        loop = asyncio.get_running_loop()
        queued_at = loop.time()
        deadline = queued_at + self._queue_timeout
        lock = _locks.setdefault(key, asyncio.Lock())
        queued = True
        key_acquired = False
        semaphore_acquired = False
        render_started_at = 0.0

        self._queued += 1
        try:
            try:
                await asyncio.wait_for(lock.acquire(), timeout=self._remaining(loop, deadline))
                key_acquired = True
                await asyncio.wait_for(self._semaphore.acquire(), timeout=self._remaining(loop, deadline))
                semaphore_acquired = True
            except (TimeoutError, asyncio.TimeoutError) as error:
                self._rejected += 1
                raise RenderQueueTimeout("绘图排队超时，请稍后再试") from error

            self._queued -= 1
            queued = False
            self._in_flight += 1
            self._started += 1
            render_started_at = loop.time()
            self._total_queue_wait += render_started_at - queued_at

            task = asyncio.current_task()
            if task is None:
                raise RuntimeError("无法获取当前绘图任务")
            expired = False

            def expire() -> None:
                nonlocal expired
                expired = True
                task.cancel()

            timeout_handle = loop.call_later(self._render_timeout, expire)
            try:
                yield
            except asyncio.CancelledError:
                if expired:
                    self._timed_out += 1
                    self._failed += 1
                    raise RenderTimeout(f"绘图超过 {self._render_timeout:g} 秒，已终止") from None
                raise
            except BaseException:
                self._failed += 1
                raise
            else:
                self._completed += 1
            finally:
                timeout_handle.cancel()
                self._total_render_time += loop.time() - render_started_at
        finally:
            if queued:
                self._queued -= 1
            if semaphore_acquired:
                self._semaphore.release()
            if key_acquired:
                lock.release()
            if render_started_at:
                self._in_flight -= 1

    def snapshot(self) -> RenderSchedulerSnapshot:
        return RenderSchedulerSnapshot(
            queued=self._queued,
            in_flight=self._in_flight,
            completed=self._completed,
            failed=self._failed,
            timed_out=self._timed_out,
            rejected=self._rejected,
            average_queue_wait=self._total_queue_wait / self._started if self._started else 0.0,
            average_render_time=self._total_render_time / self._started if self._started else 0.0,
        )

    @staticmethod
    def _remaining(loop: asyncio.AbstractEventLoop, deadline: float) -> float:
        return max(0.001, deadline - loop.time())


_render_scheduler = _RenderScheduler(
    max_concurrency=plugin_config.osu_render_max_concurrency,
    queue_size=plugin_config.osu_render_queue_size,
    queue_timeout=plugin_config.osu_render_queue_timeout,
    render_timeout=plugin_config.osu_render_timeout,
)


def render_scheduler_snapshot() -> RenderSchedulerSnapshot:
    return _render_scheduler.snapshot()


async def _drop_page(key: str) -> None:
    entry = _pages.pop(key, None)
    if entry is None:
        return
    await entry.lease.__aexit__(None, None, None)


def _file_uri_to_path(uri: str) -> Path:
    """Convert an absolute file URI generated on this host back to a path."""
    parsed = urlsplit(uri)
    path = unquote(parsed.path)
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    elif os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path)


async def _install_remote_filehost_route(page: Any, app: Any) -> None:
    """Proxy local file requests through htmlrender's configured filehost."""
    strategy = app.resources.strategy
    policy = getattr(strategy.remote_local_policy, "value", strategy.remote_local_policy)
    if not strategy.is_remote or policy != "filehost":
        return

    async def handle_local_file(route: Any) -> None:
        resolution = await app.resources.to_resource_url(
            _file_uri_to_path(route.request.url),
            strict=True,
        )
        headers = dict(resolution.request_headers_by_url.get(resolution.value, {}))
        response = await page.context.request.get(
            resolution.value,
            headers=headers,
            max_redirects=0,
        )
        try:
            await route.fulfill(response=response)
        finally:
            await response.dispose()

    await page.route("file://**", handle_local_file)


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
        await _install_remote_filehost_route(page, app)
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
    """复用模板页面；全局限流，同一模板串行，异常时自动重建。"""
    if _closing:
        raise RuntimeError("Playwright 持久页面池正在关闭")
    async with _render_scheduler.slot(key):
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
