from importlib.util import find_spec
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
