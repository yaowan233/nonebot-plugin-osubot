import asyncio
from types import SimpleNamespace

import pytest


class FakePage:
    def __init__(self):
        self.closed = False
        self.goto_calls = []
        self.reload_calls = []
        self.viewport_calls = []
        self.evaluate_calls = []

    def is_closed(self):
        return self.closed

    async def goto(self, uri, *, wait_until):
        self.goto_calls.append((uri, wait_until))

    async def set_viewport_size(self, viewport):
        self.viewport_calls.append(viewport)

    async def reload(self, *, wait_until):
        self.reload_calls.append(wait_until)

    async def evaluate(self, script, argument):
        self.evaluate_calls.append((script, argument))


class FakeLease:
    def __init__(self, enter_error=None):
        self.page = FakePage()
        self.exit_count = 0
        self.enter_error = enter_error

    async def __aenter__(self):
        if self.enter_error is not None:
            raise self.enter_error
        return self.page

    async def __aexit__(self, *_args):
        self.exit_count += 1
        self.page.closed = True


class FakePlaywright:
    def __init__(self):
        self.leases = []
        self.options = []
        self.next_enter_error = None

    def page(self, **options):
        lease = FakeLease(self.next_enter_error)
        self.next_enter_error = None
        self.leases.append(lease)
        self.options.append(options)
        return lease


@pytest.fixture
def browser_pool(monkeypatch):
    from nonebot_plugin_osubot.draw import browser

    playwright = FakePlaywright()
    app = SimpleNamespace(extensions=SimpleNamespace(playwright=playwright))
    monkeypatch.setattr(browser, "get_default_application", lambda: app)
    browser._pages.clear()
    browser._locks.clear()
    browser._closing = False
    browser._render_scheduler = browser._RenderScheduler(
        max_concurrency=2,
        queue_size=64,
        queue_timeout=1,
        render_timeout=1,
    )
    yield browser, playwright
    browser._pages.clear()
    browser._locks.clear()
    browser._closing = False


@pytest.mark.asyncio
async def test_persistent_page_reuses_lease_and_updates_viewport(browser_pool):
    browser, playwright = browser_pool

    async with browser.persistent_page("score", "file:///score.html", {"width": 100, "height": 100}) as first:
        pass
    async with browser.persistent_page("score", "file:///score.html", {"width": 200, "height": 120}) as second:
        pass

    assert first is second
    assert len(playwright.leases) == 1
    assert first.goto_calls == [("file:///score.html", "domcontentloaded")]
    assert first.reload_calls == ["domcontentloaded"]
    assert first.viewport_calls == [{"width": 200, "height": 120}]

    await browser.close_persistent_pages()
    assert playwright.leases[0].exit_count == 1


@pytest.mark.asyncio
async def test_persistent_page_drops_failed_page_and_recreates(browser_pool):
    browser, playwright = browser_pool

    with pytest.raises(RuntimeError, match="render failed"):
        async with browser.persistent_page("score", None, {"width": 100, "height": 100}):
            raise RuntimeError("render failed")

    assert playwright.leases[0].exit_count == 1
    async with browser.persistent_page("score", None, {"width": 100, "height": 100}) as page:
        assert page is playwright.leases[1].page

    await browser.close_persistent_pages()
    assert playwright.leases[1].exit_count == 1


@pytest.mark.asyncio
async def test_persistent_page_does_not_exit_lease_when_enter_fails(browser_pool):
    browser, playwright = browser_pool
    playwright.next_enter_error = RuntimeError("browser startup failed")

    with pytest.raises(RuntimeError, match="browser startup failed"):
        async with browser.persistent_page("score", None, {"width": 100, "height": 100}):
            pass

    assert playwright.leases[0].exit_count == 0
    assert "score" not in browser._pages


@pytest.mark.asyncio
async def test_wait_for_page_assets_uses_bounded_wait(browser_pool):
    browser, playwright = browser_pool

    async with browser.persistent_page("score", None, {"width": 100, "height": 100}) as page:
        await browser.wait_for_page_assets(page, timeout_ms=2500)

    script, timeout = playwright.leases[0].page.evaluate_calls[0]
    assert "Promise.race" in script
    assert "document.fonts.ready" in script
    assert timeout == 2500


@pytest.mark.asyncio
async def test_render_scheduler_limits_global_concurrency(browser_pool):
    browser, _ = browser_pool
    browser._render_scheduler = browser._RenderScheduler(
        max_concurrency=1,
        queue_size=4,
        queue_timeout=1,
        render_timeout=1,
    )
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def first_render():
        async with browser.persistent_page("first", None, {"width": 100, "height": 100}):
            first_started.set()
            await release_first.wait()

    async def second_render():
        async with browser.persistent_page("second", None, {"width": 100, "height": 100}):
            second_started.set()

    first_task = asyncio.create_task(first_render())
    await first_started.wait()
    second_task = asyncio.create_task(second_render())
    await asyncio.sleep(0)

    assert not second_started.is_set()
    assert browser.render_scheduler_snapshot().queued == 1

    release_first.set()
    await asyncio.gather(first_task, second_task)

    snapshot = browser.render_scheduler_snapshot()
    assert snapshot.completed == 2
    assert snapshot.in_flight == 0
    assert snapshot.queued == 0


@pytest.mark.asyncio
async def test_render_scheduler_rejects_when_queue_is_full(browser_pool):
    browser, _ = browser_pool
    browser._render_scheduler = browser._RenderScheduler(
        max_concurrency=1,
        queue_size=1,
        queue_timeout=1,
        render_timeout=1,
    )
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def first_render():
        async with browser.persistent_page("first", None, {"width": 100, "height": 100}):
            first_started.set()
            await release_first.wait()

    async def queued_render():
        async with browser.persistent_page("second", None, {"width": 100, "height": 100}):
            pass

    first_task = asyncio.create_task(first_render())
    await first_started.wait()
    queued_task = asyncio.create_task(queued_render())
    await asyncio.sleep(0)

    with pytest.raises(browser.RenderQueueFull, match="请求过多"):
        async with browser.persistent_page("third", None, {"width": 100, "height": 100}):
            pass

    release_first.set()
    await asyncio.gather(first_task, queued_task)
    assert browser.render_scheduler_snapshot().rejected == 1


@pytest.mark.asyncio
async def test_render_scheduler_times_out_queued_request(browser_pool):
    browser, _ = browser_pool
    browser._render_scheduler = browser._RenderScheduler(
        max_concurrency=1,
        queue_size=2,
        queue_timeout=0.01,
        render_timeout=1,
    )
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def first_render():
        async with browser.persistent_page("first", None, {"width": 100, "height": 100}):
            first_started.set()
            await release_first.wait()

    first_task = asyncio.create_task(first_render())
    await first_started.wait()

    with pytest.raises(browser.RenderQueueTimeout, match="排队超时"):
        async with browser.persistent_page("second", None, {"width": 100, "height": 100}):
            pass

    release_first.set()
    await first_task
    assert browser.render_scheduler_snapshot().rejected == 1


@pytest.mark.asyncio
async def test_render_timeout_drops_page_and_updates_metrics(browser_pool):
    browser, playwright = browser_pool
    browser._render_scheduler = browser._RenderScheduler(
        max_concurrency=1,
        queue_size=2,
        queue_timeout=1,
        render_timeout=0.01,
    )

    with pytest.raises(browser.RenderTimeout, match="已终止"):
        async with browser.persistent_page("slow", None, {"width": 100, "height": 100}):
            await asyncio.Event().wait()

    assert playwright.leases[0].exit_count == 1
    snapshot = browser.render_scheduler_snapshot()
    assert snapshot.failed == 1
    assert snapshot.timed_out == 1
    assert snapshot.in_flight == 0

    async with browser.persistent_page("slow", None, {"width": 100, "height": 100}) as page:
        assert page is playwright.leases[1].page
