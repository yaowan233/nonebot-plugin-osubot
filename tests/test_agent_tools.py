import json
from importlib.util import find_spec
from io import BytesIO
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.skipif(
    find_spec("langchain") is None or find_spec("nonebot_plugin_ai_groupmate") is None,
    reason="ai-groupmate agent integration is an optional dependency",
)


def test_self_reference_placeholders_fall_back_to_bound_context():
    from nonebot_plugin_osubot.agent_tools import (
        _clean_user_id,
        _clean_optional_text,
    )

    for value in ("我", "当前用户", "current_user", "current user", "requester"):
        assert _clean_optional_text(value) is None
        assert _clean_user_id(value) is None


def test_osu_tool_instructions_do_not_ask_model_for_current_user_id():
    from nonebot_plugin_osubot.agent_tools import build_osu_agent_tools

    context = SimpleNamespace(user_id="12345678")
    bundle = build_osu_agent_tools(context)
    instructions = "\n".join(bundle.instructions)

    assert "发言用户 ID 已由系统在工具上下文中绑定" in instructions
    assert "禁止追问或猜测个人 ID" in instructions
    assert "不要传 username 或 target_user_id" in instructions

    bp_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_bp")
    schema = bp_tool.args_schema.model_json_schema()
    assert "查询当前发言用户时必须省略" in schema["properties"]["target_user_id"]["description"]
    assert "查询当前发言用户" in schema["properties"]["username"]["description"]
    assert schema["properties"]["purpose"]["enum"] == ["view", "analyze"]
    assert "include_image_for_analysis" not in schema["properties"]
    assert any(tool.name == "get_osu_bp_data" for tool in bundle.tools)
    assert "比较多个 BP" in instructions


@pytest.mark.asyncio
async def test_send_osu_bp_returns_structured_analysis_and_only_sends_once(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    score = SimpleNamespace(
        beatmap=SimpleNamespace(
            id=1,
            set_id=2,
            artist="artist",
            title="title",
            version="difficulty",
            creator="mapper",
            stars=6.543,
            bpm=180,
            total_length=120,
        ),
        statistics=SimpleNamespace(
            model_dump=lambda **_: {"great": 1000, "miss": 1}
        ),
        rank="A",
        pp=321.456,
        accuracy=98.76543,
        max_combo=1234,
        mods=[SimpleNamespace(acronym="HD")],
        total_score=987654,
        ended_at=SimpleNamespace(isoformat=lambda: "2026-07-31T12:00:00"),
        score_version="lazer",
    )
    calls = {"draw": 0, "send": 0}

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_draw(*args, **kwargs):
        calls["draw"] += 1
        return BytesIO(b"image"), score

    async def fake_send(*args, **kwargs):
        calls["send"] += 1
        return "已发送图片"

    async def fake_active(*args, **kwargs):
        return True

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "draw_score", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    monkeypatch.setattr(agent_tools, "is_request_active", fake_active)

    context = SimpleNamespace(
        user_id="12345678",
        request_id="request-1",
        session_id="group-1",
        send_target=None,
    )
    bundle = agent_tools.build_osu_agent_tools(context)
    bp_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_bp")

    first = json.loads(await bp_tool.ainvoke({"best": 10, "purpose": "analyze"}))
    second = json.loads(await bp_tool.ainvoke({"best": 10, "purpose": "analyze"}))

    assert first["status"] == "sent"
    assert first["next_action"] == "reply_with_analysis"
    assert first["scores"][0]["score"]["miss"] == 1
    assert first["scores"][0]["score"]["pp"] == 321.46
    assert second["status"] == "already_sent"
    assert calls == {"draw": 1, "send": 1}


@pytest.mark.asyncio
async def test_get_osu_bp_data_reads_multiple_scores_without_sending(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_query(*args, **kwargs):
        assert args[-1] == [1, 10]
        return [{"bp_index": 1}, {"bp_index": 10}]

    async def fake_send(*args, **kwargs):
        raise AssertionError("纯数据工具不应发送图片")

    async def fake_active(*args, **kwargs):
        return True

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "_query_bp_scores", fake_query)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    monkeypatch.setattr(agent_tools, "is_request_active", fake_active)

    context = SimpleNamespace(
        user_id="12345678",
        request_id="request-1",
        session_id="group-1",
        send_target=None,
    )
    bundle = agent_tools.build_osu_agent_tools(context)
    data_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_bp_data")

    result = json.loads(await data_tool.ainvoke({"best_indices": [1, 10]}))

    assert result["status"] == "ok"
    assert result["scores"] == [{"bp_index": 1}, {"bp_index": 10}]
    assert "未发送图片" in result["message"]
