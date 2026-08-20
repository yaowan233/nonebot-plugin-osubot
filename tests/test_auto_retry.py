import asyncio

import httpx
import pytest


def _response(status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        headers=headers,
        request=httpx.Request("GET", "https://example.com/resource"),
    )


def _policy(sleeps: list[float], *, max_attempts: int = 3):
    from nonebot_plugin_osubot.network.auto_retry import RetryPolicy

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    return RetryPolicy(
        max_attempts=max_attempts,
        base_delay=0.5,
        max_delay=8,
        jitter_ratio=0.2,
        sleep=sleep,
        jitter=lambda _start, _end: 0,
    )


@pytest.mark.asyncio
async def test_retry_policy_retries_transport_errors_with_exponential_backoff(after_nonebot_init):
    sleeps: list[float] = []
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ReadTimeout(
                "timed out",
                request=httpx.Request("GET", "https://example.com/resource"),
            )
        return "ok"

    assert await _policy(sleeps).run(operation, operation_name="test") == "ok"
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_retry_policy_honours_retry_after_for_rate_limits(after_nonebot_init):
    sleeps: list[float] = []
    responses = [_response(429, {"Retry-After": "2.5"}), _response(200)]

    async def operation():
        return responses.pop(0)

    response = await _policy(sleeps).run(operation)

    assert response.status_code == 200
    assert sleeps == [2.5]


@pytest.mark.asyncio
async def test_retry_policy_retries_server_errors_but_returns_last_response(after_nonebot_init):
    sleeps: list[float] = []
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        return _response(503)

    response = await _policy(sleeps).run(operation)

    assert response.status_code == 503
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_retry_policy_does_not_retry_client_or_programming_errors(after_nonebot_init):
    sleeps: list[float] = []
    attempts = 0

    async def client_error():
        nonlocal attempts
        attempts += 1
        return _response(404)

    assert (await _policy(sleeps).run(client_error)).status_code == 404
    assert attempts == 1

    async def programming_error():
        raise ValueError("bad argument")

    with pytest.raises(ValueError, match="bad argument"):
        await _policy(sleeps).run(programming_error)

    assert sleeps == []


@pytest.mark.asyncio
async def test_retry_policy_reraises_final_network_error(after_nonebot_init):
    sleeps: list[float] = []
    error = httpx.ConnectError(
        "offline",
        request=httpx.Request("GET", "https://example.com/resource"),
    )

    async def operation():
        raise error

    with pytest.raises(httpx.ConnectError) as raised:
        await _policy(sleeps).run(operation)

    assert raised.value is error
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_retry_policy_never_swallows_cancellation(after_nonebot_init):
    sleeps: list[float] = []

    async def operation():
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _policy(sleeps).run(operation)

    assert sleeps == []
