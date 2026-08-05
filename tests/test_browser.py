from types import SimpleNamespace

import pytest


class FakePage:
    def __init__(self):
        self.closed = False
        self.goto_calls = []
        self.viewport_calls = []
        self.evaluate_calls = []

    def is_closed(self):
        return self.closed

    async def goto(self, uri, *, wait_until):
        self.goto_calls.append((uri, wait_until))

    async def set_viewport_size(self, viewport):
        self.viewport_calls.append(viewport)

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
