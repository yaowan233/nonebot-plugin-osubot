import asyncio

import httpx
import pytest


def _response(status_code: int, url: str) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", url), content=str(status_code).encode())


@pytest.mark.asyncio
async def test_mirror_racer_cancels_and_awaits_losing_requests(after_nonebot_init):
    from nonebot_plugin_osubot.network.first_response import MirrorRacer

    slow_url = "https://slow.example/map"
    fast_url = "https://fast.example/map"

    class FakeClient:
        def __init__(self):
            self.slow_started = asyncio.Event()
            self.slow_cancelled = asyncio.Event()

        async def get(self, url: str, *, timeout: float):
            assert timeout == 3.0
            if url == fast_url:
                return _response(200, url)
            self.slow_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.slow_cancelled.set()
                raise

    client = FakeClient()
    provider_calls = 0

    async def get_client():
        nonlocal provider_calls
        provider_calls += 1
        return client

    racer = MirrorRacer(get_client, hedge_delay=0)
    response = await racer.request([slow_url, fast_url], timeout=3.0)

    assert response is not None
    assert response.request.url == fast_url
    assert client.slow_started.is_set()
    assert client.slow_cancelled.is_set()
    assert provider_calls == 1


@pytest.mark.asyncio
async def test_mirror_racer_learns_to_try_recently_healthy_origin_first(after_nonebot_init):
    from nonebot_plugin_osubot.network.first_response import MirrorRacer

    bad_url = "https://bad.example/map"
    good_url = "https://good.example/map"

    class FakeClient:
        def __init__(self):
            self.calls: list[str] = []

        async def get(self, url: str, *, timeout: float):
            self.calls.append(url)
            return _response(503 if url == bad_url else 200, url)

    client = FakeClient()

    async def get_client():
        return client

    racer = MirrorRacer(get_client, hedge_delay=1)
    first = await racer.request([bad_url, good_url])
    assert first is not None
    assert client.calls == [bad_url, good_url]

    client.calls.clear()
    second = await racer.request([bad_url, good_url])

    assert second is not None
    assert second.request.url == good_url
    assert client.calls == [good_url]


@pytest.mark.asyncio
async def test_mirror_racer_continues_after_http_error(after_nonebot_init):
    from nonebot_plugin_osubot.network.first_response import MirrorRacer

    failed_url = "https://failed.example/map"
    healthy_url = "https://healthy.example/map"

    class FakeClient:
        async def get(self, url: str, *, timeout: float):
            if url == failed_url:
                raise httpx.ConnectError("offline", request=httpx.Request("GET", url))
            return _response(200, url)

    async def get_client():
        return FakeClient()

    response = await MirrorRacer(get_client, hedge_delay=1).request([failed_url, healthy_url])

    assert response is not None
    assert response.request.url == healthy_url


@pytest.mark.asyncio
async def test_cancelling_mirror_race_cleans_up_every_request(after_nonebot_init):
    from nonebot_plugin_osubot.network.first_response import MirrorRacer

    class BlockingClient:
        def __init__(self):
            self.started = 0
            self.all_started = asyncio.Event()
            self.cancelled = 0

        async def get(self, url: str, *, timeout: float):
            self.started += 1
            if self.started == 2:
                self.all_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise

    client = BlockingClient()

    async def get_client():
        return client

    task = asyncio.create_task(
        MirrorRacer(get_client, hedge_delay=0).request(["https://one.example/map", "https://two.example/map"])
    )
    await asyncio.wait_for(client.all_started.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert client.cancelled == 2
