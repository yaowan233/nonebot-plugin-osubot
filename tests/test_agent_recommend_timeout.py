import asyncio
import json
from importlib.util import find_spec
from types import SimpleNamespace
from io import BytesIO
from unittest.mock import AsyncMock

import pytest


pytestmark = pytest.mark.skipif(
    find_spec("langchain") is None or find_spec("nonebot_plugin_ai_groupmate") is None,
    reason="optional AI integration dependencies unavailable",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_stage", ["lookup", "recommend", "render"])
async def test_slow_recommendation_returns_before_tool_deadline_and_delivers_once(monkeypatch, slow_stage):
    from nonebot_plugin_osubot import agent_tools

    release = asyncio.Event()
    delivered = asyncio.Event()
    calls = []
    original_wait = asyncio.wait

    async def short_wait(tasks, *, timeout=None, **kwargs):
        return await original_wait(tasks, timeout=0.01, **kwargs)

    async def resolve(*args, **kwargs):
        if slow_stage == "lookup":
            await release.wait()
        return agent_tools.ResolvedOsuUser(42, "player")

    async def recommend(*args, **kwargs):
        calls.append(kwargs)
        if slow_stage == "recommend":
            await release.wait()
        return SimpleNamespace(recommendations=[object()])

    async def draw(*args, **kwargs):
        if slow_stage == "render":
            await release.wait()
        return BytesIO(b"image")

    async def send(*args, **kwargs):
        delivered.set()

    monkeypatch.setattr(agent_tools.asyncio, "wait", short_wait)
    monkeypatch.setattr(agent_tools.UniMessage, "send", AsyncMock())
    monkeypatch.setattr(agent_tools, "_resolve_osu_user", resolve)
    monkeypatch.setattr(agent_tools, "get_recommend", recommend)
    monkeypatch.setattr(agent_tools, "draw_recommend", draw)
    monkeypatch.setattr(agent_tools, "_send_image", send)
    monkeypatch.setattr(agent_tools, "_send_text", send)
    monkeypatch.setattr(agent_tools, "_recommend_to_summary", lambda data: {})
    context = SimpleNamespace(session_id=f"slow-{slow_stage}", user_id="1", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    tool = next(item for item in bundle.tools if item.name == "send_osu_recommend")
    try:
        response = await asyncio.wait_for(tool.ainvoke({"mode": "mania"}), timeout=2)
        assert json.loads(response)["status"] == "pending"
        from nonebot_plugin_ai_groupmate.agent.tool_results import parse_tool_result

        parsed = parse_tool_result(response)
        assert parsed["status"] == "succeeded"
        assert parsed["reason_code"] == "recommendation_queued"
        assert parsed["data"]["image_sent"] is False
        assert not delivered.is_set()
        next_bundle = agent_tools.build_osu_agent_tools(context)
        next_tool = next(item for item in next_bundle.tools if item.name == "send_osu_recommend")
        repeated = await next_tool.ainvoke({"mode": "mania"})
        assert json.loads(repeated)["status"] == "pending"
        assert len(calls) == (0 if slow_stage == "lookup" else 1)
        release.set()
        await asyncio.wait_for(delivered.wait(), timeout=1)
    finally:
        release.set()


@pytest.mark.asyncio
async def test_repeated_recommendation_across_chat_turns_sends_once(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    monkeypatch.setattr(
        agent_tools, "_resolve_osu_user", AsyncMock(return_value=agent_tools.ResolvedOsuUser(42, "player"))
    )
    monkeypatch.setattr(
        agent_tools, "get_recommend", AsyncMock(return_value=SimpleNamespace(recommendations=[object()]))
    )
    monkeypatch.setattr(agent_tools, "draw_recommend", AsyncMock(return_value=BytesIO(b"image")))
    send = AsyncMock()
    monkeypatch.setattr(agent_tools, "_send_image", send)
    monkeypatch.setattr(agent_tools, "_recommend_to_summary", lambda data: {})

    async def invoke(session, user, **arguments):
        context = SimpleNamespace(session_id=session, user_id=user, bot_id="bot", send_target=None)
        bundle = agent_tools.build_osu_agent_tools(context)
        tool = next(item for item in bundle.tools if item.name == "send_osu_recommend")
        return await tool.ainvoke(arguments)

    await invoke("dedup-chat", "1", mode="mania", target="mixed")
    await invoke("dedup-chat", "1", mode="3", target="balanced", include_image_for_analysis=True)
    assert send.await_count == 1
    await invoke("dedup-chat", "1", mode="mania", filters={"key_counts": [7]})
    await invoke("other-chat", "1", mode="mania")
    await invoke("dedup-chat", "2", mode="mania")
    assert send.await_count == 4


@pytest.mark.asyncio
async def test_expired_ai_request_does_not_submit_recommendation(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    resolve = AsyncMock()
    monkeypatch.setattr(agent_tools, "_resolve_osu_user", resolve)
    monkeypatch.setattr(agent_tools, "_is_context_request_active", AsyncMock(return_value=False))
    bundle = agent_tools.build_osu_agent_tools(SimpleNamespace(user_id="1", request_id="expired", send_target=None))
    tool = next(item for item in bundle.tools if item.name == "send_osu_recommend")
    assert json.loads(await tool.ainvoke({}))["status"] == "expired"
    resolve.assert_not_awaited()
