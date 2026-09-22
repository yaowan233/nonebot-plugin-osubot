import asyncio
import json

import pytest


@pytest.mark.asyncio
async def test_completed_delivery_is_reused_without_sending_again(monkeypatch):
    from nonebot_plugin_osubot.agent_recommend_delivery import RecommendationDelivery

    calls = []

    async def operation():
        calls.append("send")
        return "sent"

    async def notify(result):
        calls.append("notify")

    delivery = RecommendationDelivery()
    assert await delivery.submit("same", operation, notify) == "sent"
    assert await delivery.submit("same", operation, notify) == "sent"
    assert calls == ["send"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_deferred_failure_notifies_and_releases_capacity(monkeypatch, failure):
    from nonebot_plugin_osubot import agent_recommend_delivery as module

    monkeypatch.setattr(module, "QUICK_WAIT_SECONDS", 0.001)
    monkeypatch.setattr(module, "DELIVERY_TIMEOUT_SECONDS", 0.05)
    release = asyncio.Event()
    notices = []

    async def operation():
        await release.wait()
        if failure:
            raise RuntimeError("private backend failure")

    async def notify(result):
        notices.append(json.loads(result))

    delivery = module.RecommendationDelivery()
    assert json.loads(await delivery.submit("job", operation, notify))["status"] == "pending"
    if failure:
        release.set()
    await asyncio.wait_for(delivery.tasks["job"], timeout=1)
    await asyncio.sleep(0)
    assert notices[0]["status"] == "failed"
    assert "private" not in notices[0]["message"]
    assert "job" not in delivery.tasks


@pytest.mark.asyncio
async def test_completed_delivery_expires_and_failure_can_retry(monkeypatch):
    from nonebot_plugin_osubot import agent_recommend_delivery as module

    callbacks = []
    loop = asyncio.get_running_loop()
    original_call_later = loop.call_later

    def capture_expiry(delay, callback, *args, **kwargs):
        if callback.__name__ == "forget":
            callbacks.append((callback, args))
            return None
        return original_call_later(delay, callback, *args, **kwargs)

    monkeypatch.setattr(loop, "call_later", capture_expiry)
    delivery = module.RecommendationDelivery()
    calls = []

    async def operation():
        calls.append(1)
        return "sent"

    async def notify(result):
        pass

    await delivery.submit("job", operation, notify)
    await delivery.submit("job", operation, notify)
    assert len(calls) == 1
    callback, arguments = callbacks.pop()
    callback(*arguments)
    await delivery.submit("job", operation, notify)
    assert len(calls) == 2

    async def failure():
        return '{"status":"failed"}'

    await delivery.submit("failure", failure, notify)
    await delivery.submit("failure", operation, notify)
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_outer_cancellation_before_acceptance_cancels_child(monkeypatch):
    from nonebot_plugin_osubot import agent_recommend_delivery as module

    monkeypatch.setattr(module, "QUICK_WAIT_SECONDS", 10)
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def operation():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def notify(result):
        raise AssertionError("unaccepted task must not notify")

    delivery = module.RecommendationDelivery()
    caller = asyncio.create_task(delivery.submit("job", operation, notify))
    await started.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert stopped.is_set()
    assert "job" not in delivery.tasks


@pytest.mark.asyncio
async def test_background_capacity_is_bounded(monkeypatch):
    from nonebot_plugin_osubot import agent_recommend_delivery as module

    monkeypatch.setattr(module, "QUICK_WAIT_SECONDS", 0.001)
    monkeypatch.setattr(module, "MAX_ACTIVE_TASKS", 1)
    release = asyncio.Event()
    calls = []

    async def operation():
        calls.append(1)
        await release.wait()
        return "sent"

    async def notify(result):
        pass

    first, second = module.RecommendationDelivery(), module.RecommendationDelivery()
    try:
        assert json.loads(await first.submit("one", operation, notify))["status"] == "pending"
        assert json.loads(await second.submit("two", operation, notify))["status"] == "busy"
        assert calls == [1]
    finally:
        release.set()
        await first.tasks["one"]
