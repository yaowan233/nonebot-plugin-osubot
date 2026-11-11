from importlib.util import find_spec
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.skipif(
    find_spec("langchain") is None or find_spec("nonebot_plugin_ai_groupmate") is None,
    reason="ai-groupmate agent integration is an optional dependency",
)


def test_osu_tools_are_partitioned_into_small_discoverable_groups():
    from nonebot_plugin_osubot import agent_tools

    if "tools" not in getattr(agent_tools.AgentSkill, "__dataclass_fields__", {}):
        pytest.skip("host does not support deferred skill tools")
    bundle = agent_tools.build_osu_agent_tools(SimpleNamespace(user_id="123"))
    groups = {skill.name: {tool.name for tool in skill.tools} for skill in bundle.skills}
    all_names = [tool.name for tool in bundle.tools]
    assert bundle.defer_instructions
    assert len(all_names) == 23
    assert len(set(all_names)) == 23
    assert set().union(*groups.values()) == set(all_names)
    assert sum(map(len, groups.values())) == len(all_names)
    assert max(map(len, groups.values())) <= 5
    assert "send_osu_bp" in groups["osu_bp"]
    assert "send_osu_replay_analysis" in groups["osu_replay"]
    assert "send_osu_recommend" in groups["osu_recommend"]
    prompts = {skill.name: skill.prompt for skill in bundle.skills}
    assert "禁止追问或猜测个人 ID" in prompts["osu_bp"]
    assert "send_osu_replay_analysis" in prompts["osu_replay"]
    assert "send_osu_recommend" not in prompts["osu_replay"]


def test_osu_tools_fall_back_for_older_host(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    monkeypatch.setattr(agent_tools, "AgentSkill", None)
    bundle = agent_tools.build_osu_agent_tools(SimpleNamespace(user_id="123"))
    assert len(list(bundle.tools)) == 23
    assert not bundle.skills
    assert list(bundle.instructions)


def test_missing_optional_replay_tool_keeps_other_tools_deferred():
    from dataclasses import replace

    from nonebot_plugin_osubot import agent_tools

    if "tools" not in getattr(agent_tools.AgentSkill, "__dataclass_fields__", {}):
        pytest.skip("host does not support deferred skill tools")
    bundle = agent_tools.build_osu_agent_tools(SimpleNamespace(user_id="123"))
    legacy = replace(bundle, tools=[t for t in bundle.tools if t.name != "send_osu_replay_analysis"],
                     skills=[], defer_instructions=False)
    result = agent_tools._defer_osu_tools(legacy)
    assert result.defer_instructions
    assert "osu_replay" not in {skill.name for skill in result.skills}
    assert {tool.name for skill in result.skills for tool in skill.tools} == {tool.name for tool in legacy.tools}


def test_unrecognized_tool_keeps_original_bundle():
    from dataclasses import replace

    from nonebot_plugin_osubot import agent_tools

    bundle = agent_tools.build_osu_agent_tools(SimpleNamespace(user_id="123"))
    original = replace(bundle, tools=[*bundle.tools, SimpleNamespace(name="future_osu_tool")],
                       skills=[], defer_instructions=False)
    assert agent_tools._defer_osu_tools(original) is original


@pytest.mark.asyncio
async def test_real_osu_registration_is_deferred_in_chat_graph(monkeypatch):
    from unittest.mock import AsyncMock

    from nonebot_plugin_ai_groupmate import agent
    from nonebot_plugin_ai_groupmate.agent import custom_tools
    from nonebot_plugin_osubot import agent_tools

    monkeypatch.setattr(custom_tools, "_registered_agent_tool_factories", [agent_tools.build_osu_agent_tools])
    monkeypatch.setattr(agent.plugin_config, "agent_file_tools_enabled", False)
    for name in ("get_user_relation_context", "get_group_context", "get_recent_relations_context", "relevant_context"):
        monkeypatch.setattr(agent, name, AsyncMock(return_value=""))
    monkeypatch.setattr(agent, "get_chat_model", lambda: object())
    monkeypatch.setattr(agent, "load_group_style_context", AsyncMock(return_value=""))
    captured = {}

    def build(_model, tools, prompt, **kwargs):
        captured.update(tools=tools, prompt=prompt, **kwargs)
        return object()

    monkeypatch.setattr(agent, "build_chat_graph", build)
    await agent.create_chat_graph(SimpleNamespace(commit=AsyncMock()), "group", None, "123", "User", history=[],
                                  group_members=[])  # pyright: ignore[reportArgumentType]
    visible = {tool.name for tool in captured["base_tools"]}
    all_tools = {tool.name for tool in captured["tools"]}
    assert "send_osu_bp" not in visible
    assert "send_osu_replay_analysis" not in visible
    assert "send_osu_bp" in all_tools
    assert "send_osu_replay_analysis" in all_tools
    assert {tool.name for tool in captured["tools_by_skill"]["osu_bp"]} >= {"send_osu_bp", "get_osu_bp_data"}
    assert {tool.name for tool in captured["tools_by_skill"]["osu_replay"]} == {"send_osu_replay_analysis"}
    prompt = str(captured["prompt"])
    assert "osu_bp" in prompt
    assert "禁止追问或猜测个人 ID" not in prompt
    lazy_count = len(visible)
    monkeypatch.setattr(agent_tools, "AgentSkill", None)
    captured.clear()
    await agent.create_chat_graph(SimpleNamespace(commit=AsyncMock()), "group", None, "123", "User", history=[],
                                  group_members=[])  # pyright: ignore[reportArgumentType]
    legacy_visible = {tool.name for tool in captured["base_tools"]}
    assert "send_osu_bp" in legacy_visible
    assert len(legacy_visible) - lazy_count == 23
