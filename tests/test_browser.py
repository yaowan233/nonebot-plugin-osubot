from types import SimpleNamespace

import pytest


class FakePage:
    def __init__(self):
        self.closed = False
        self.goto_calls = []
        self.viewport_calls = []

    def is_closed(self):
        return self.closed

    async def goto(self, uri, *, wait_until):
        self.goto_calls.append((uri, wait_until))

    async def set_viewport_size(self, viewport):
        self.viewport_calls.append(viewport)


class FakeLease:
    def __init__(self):
        self.page = FakePage()
        self.exit_count = 0

    async def __aenter__(self):
        return self.page

    async def __aexit__(self, *_args):
        self.exit_count += 1
        self.page.closed = True


class FakePlaywright:
    def __init__(self):
        self.leases = []
        self.options = []

    def page(self, **options):
        lease = FakeLease()
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
    assert first.goto_calls == [("file:///score.html", "load")]
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
