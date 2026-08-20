import asyncio

import httpx
import pytest


def _response(status_code: int, *, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        headers=headers,
        request=httpx.Request("GET", "https://osu.ppy.sh/api/v2/test"),
    )


@pytest.mark.asyncio
async def test_foreground_request_is_not_blocked_by_background_work():
    from nonebot_plugin_osubot.network.scheduler import (
        OsuApiScheduler,
        RequestPriority,
        osu_api_priority,
    )

    scheduler = OsuApiScheduler(
        max_concurrency=2,
        foreground_rate=10_000,
        background_rate=10_000,
    )
    background_started = asyncio.Event()
    release_background = asyncio.Event()

    async def background_operation():
        background_started.set()
        await release_background.wait()
        return _response(200)

    async def foreground_operation():
        return _response(204)

    try:
        with osu_api_priority(RequestPriority.BACKGROUND):
            background = asyncio.create_task(scheduler.request(background_operation))
        await background_started.wait()

        foreground = await asyncio.wait_for(scheduler.request(foreground_operation), timeout=0.5)
        assert foreground.status_code == 204
        assert not background.done()

        release_background.set()
        assert (await background).status_code == 200
        assert scheduler.snapshot().completed == 2
    finally:
        release_background.set()
        await scheduler.close()


@pytest.mark.asyncio
async def test_scheduler_retries_429_and_5xx_but_not_404():
    from nonebot_plugin_osubot.network.scheduler import OsuApiScheduler

    delays = []

    async def fake_sleep(delay: float):
        delays.append(delay)

    scheduler = OsuApiScheduler(
        max_concurrency=2,
        foreground_rate=100_000,
        background_rate=100_000,
        max_retries=3,
        retry_base_delay=0.5,
        sleep=fake_sleep,
    )
    responses = [
        _response(429, headers={"Retry-After": "2"}),
        _response(503),
        _response(200),
    ]
    calls = 0

    async def eventually_succeeds():
        nonlocal calls
        response = responses[calls]
        calls += 1
        return response

    not_found_calls = 0

    async def not_found():
        nonlocal not_found_calls
        not_found_calls += 1
        return _response(404)

    try:
        assert (await scheduler.request(eventually_succeeds)).status_code == 200
        assert (await scheduler.request(not_found)).status_code == 404
        assert calls == 3
        assert not_found_calls == 1
        assert any(delay == pytest.approx(2.0, abs=0.01) for delay in delays)
        assert 1.0 in delays
        snapshot = scheduler.snapshot()
        assert snapshot.retried == 2
        assert snapshot.rate_limited == 1
    finally:
        await scheduler.close()


@pytest.mark.asyncio
async def test_scheduler_retries_transport_errors_and_then_propagates():
    from nonebot_plugin_osubot.network.scheduler import OsuApiScheduler

    async def fake_sleep(_delay: float):
        return None

    scheduler = OsuApiScheduler(
        max_concurrency=2,
        foreground_rate=100_000,
        background_rate=100_000,
        max_retries=2,
        sleep=fake_sleep,
    )
    calls = 0

    async def unavailable():
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline")

    try:
        with pytest.raises(httpx.ConnectError, match="offline"):
            await scheduler.request(unavailable)
        assert calls == 3
        assert scheduler.snapshot().failed == 1
        assert scheduler.snapshot().retried == 2
    finally:
        await scheduler.close()


@pytest.mark.asyncio
async def test_background_queue_is_bounded():
    from nonebot_plugin_osubot.network.scheduler import ApiQueueFull, OsuApiScheduler, RequestPriority

    scheduler = OsuApiScheduler(
        max_concurrency=2,
        foreground_rate=10_000,
        background_rate=10_000,
        queue_size=1,
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked():
        started.set()
        await release.wait()
        return _response(200)

    async def queued():
        return _response(200)

    first = asyncio.create_task(scheduler.request(blocked, priority=RequestPriority.BACKGROUND))
    second = None
    try:
        await started.wait()
        second = asyncio.create_task(scheduler.request(queued, priority=RequestPriority.BACKGROUND))
        while scheduler.snapshot().background_queued < 1:
            await asyncio.sleep(0)

        with pytest.raises(ApiQueueFull, match="background queue"):
            await scheduler.request(queued, priority=RequestPriority.BACKGROUND)
    finally:
        release.set()
        await first
        if second is not None:
            await second
        await scheduler.close()


@pytest.mark.asyncio
async def test_safe_async_get_schedules_only_official_api_requests(monkeypatch):
    import nonebot_plugin_osubot.api as api

    scheduled = []
    direct = []

    async def schedule(operation):
        scheduled.append(True)
        return _response(200)

    async def direct_get(url, headers=None, params=None):
        direct.append(url)
        return _response(200)

    monkeypatch.setattr(api.osu_api_scheduler, "request", schedule)
    monkeypatch.setattr(api, "_direct_async_get", direct_get)

    await api.safe_async_get("https://osu.ppy.sh/api/v2/users/2")
    await api.safe_async_get("https://osekai.net/medals/api/public/get_medal.php")

    assert scheduled == [True]
    assert direct == ["https://osekai.net/medals/api/public/get_medal.php"]


@pytest.mark.asyncio
async def test_concurrent_header_requests_share_one_token_refresh(monkeypatch):
    import nonebot_plugin_osubot.api as api

    calls = 0
    api.cache.clear()

    async def renew():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        api.cache["token"] = "shared-token"

    monkeypatch.setattr(api, "renew_token", renew)
    try:
        headers = await asyncio.gather(*(api.get_headers() for _ in range(10)))
    finally:
        api.cache.clear()

    assert calls == 1
    assert {item["Authorization"] for item in headers} == {"Bearer shared-token"}
