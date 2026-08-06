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
    assert any(tool.name == "search_osu_beatmaps" for tool in bundle.tools)
    assert any(tool.name == "get_osu_scores_by_map_name" for tool in bundle.tools)
    assert "比较多个 BP" in instructions
    assert "所有候选难度及成绩用简洁列表一次展示" in instructions


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
        statistics=SimpleNamespace(model_dump=lambda **_: {"great": 1000, "miss": 1}),
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


@pytest.mark.asyncio
async def test_search_osu_beatmaps_returns_score_tool_candidates(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    async def fake_search(query: str):
        assert query == "Freedom Dive"
        return [
            {
                "id": 10,
                "artist": "xi",
                "title": "FREEDOM DiVE",
                "creator": "Nakagawa-Kanon",
                "status": "ranked",
                "beatmaps": [
                    {"id": 101, "mode_int": 1, "version": "Taiko Oni", "difficulty_rating": 5.1},
                    {"id": 102, "mode_int": 0, "version": "FOUR DIMENSIONS", "difficulty_rating": 7.8},
                    {"id": 103, "mode_int": 3, "version": "Another", "difficulty_rating": 6.2},
                ],
            }
        ]

    monkeypatch.setattr(agent_tools, "search_beatmapsets", fake_search)
    context = SimpleNamespace(user_id="12345678")
    bundle = agent_tools.build_osu_agent_tools(context)
    search_tool = next(tool for tool in bundle.tools if tool.name == "search_osu_beatmaps")

    result = json.loads(await search_tool.ainvoke({"query": "Freedom Dive", "mode": "3"}))

    assert result["status"] == "ok"
    assert result["mode"] == "mania"
    assert [item["beatmap_id"] for item in result["candidates"]] == [103, 102]
    assert result["candidates"][0]["difficulty"] == "Another"
    assert result["candidates"][1]["native_mode"] == "osu"


@pytest.mark.asyncio
async def test_get_osu_scores_by_map_name_sends_image_for_only_played_difficulty(monkeypatch):
    from nonebot_plugin_osubot import agent_tools
    from nonebot_plugin_osubot.exceptions import NetworkError

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player", "3")

    async def fake_search(query: str):
        assert query == "Freedom Dive"
        return [
            {
                "id": 10,
                "artist": "xi",
                "title": "FREEDOM DiVE",
                "creator": "Nakagawa-Kanon",
                "status": "ranked",
                "beatmaps": [
                    {"id": 101, "mode_int": 3, "version": "Another", "difficulty_rating": 6.2},
                    {"id": 102, "mode_int": 0, "version": "FOUR DIMENSIONS", "difficulty_rating": 7.8},
                ],
            }
        ]

    async def fake_osu_api(project, uid, mode, map_id, **kwargs):
        assert (project, uid, mode) == ("best_score", 42, "mania")
        if map_id == 102:
            raise NetworkError("未找到该地图成绩")
        return {
            "position": 123,
            "score": {
                "rank": "A",
                "pp": 321.456,
                "accuracy": 0.987654,
                "max_combo": 1000,
                "statistics": {"miss": 2},
                "mods": [{"acronym": "HD"}],
                "total_score": 987654,
                "ended_at": "2026-08-06T00:00:00Z",
                "legacy_score_id": None,
            },
        }

    async def fake_get_score_data(*args, **kwargs):
        assert args[0] == 42
        assert args[2] == "mania"
        assert args[4] == 101
        return BytesIO(b"score-image")

    sent = []

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "search_beatmapsets", fake_search)
    monkeypatch.setattr(agent_tools, "osu_api", fake_osu_api)
    monkeypatch.setattr(agent_tools, "get_score_data", fake_get_score_data)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    score_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_scores_by_map_name")

    result = json.loads(await score_tool.ainvoke({"query": "Freedom Dive"}))

    assert result["status"] == "sent"
    assert result["player"] == "player"
    assert result["next_action"] == "finish"
    assert result["selected"]["score"]["pp"] == 321.46
    assert result["selected"]["score"]["miss"] == 2
    assert sent == [b"score-image"]


@pytest.mark.asyncio
async def test_get_osu_scores_by_map_name_keeps_list_when_multiple_scores_exist(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player", "0")

    async def fake_search(query: str):
        return [
            {
                "id": 10,
                "artist": "artist",
                "title": query,
                "creator": "mapper",
                "status": "ranked",
                "beatmaps": [
                    {"id": 101, "mode_int": 0, "version": "Hard", "difficulty_rating": 4.0},
                    {"id": 102, "mode_int": 0, "version": "Insane", "difficulty_rating": 5.0},
                ],
            }
        ]

    async def fake_osu_api(*args, **kwargs):
        map_id = args[3]
        return {
            "score": {
                "rank": "A",
                "pp": float(map_id),
                "accuracy": 0.98,
                "max_combo": 500,
                "statistics": {"miss": 1},
                "mods": [],
                "total_score": 1000000,
                "ended_at": "2026-08-06T00:00:00Z",
                "legacy_score_id": None,
            }
        }

    async def fail_send(*args, **kwargs):
        raise AssertionError("多个成绩时不应直接发送图片")

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "search_beatmapsets", fake_search)
    monkeypatch.setattr(agent_tools, "osu_api", fake_osu_api)
    monkeypatch.setattr(agent_tools, "_send_image", fail_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    score_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_scores_by_map_name")

    result = json.loads(await score_tool.ainvoke({"query": "Test Song"}))

    assert result["status"] == "ok"
    assert result["played_count"] == 2
    assert [item["difficulty"] for item in result["results"]] == ["Hard", "Insane"]


@pytest.mark.asyncio
async def test_send_osu_bp_list_sends_single_score_when_filter_has_one_result(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    score = SimpleNamespace()

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player", "0")

    async def fake_select(*args, **kwargs):
        return [score], [score]

    async def fake_single(*args, **kwargs):
        return BytesIO(b"single-score"), score

    sent = []

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "select_bp_scores", fake_select)
    monkeypatch.setattr(agent_tools, "draw_selected_score", fake_single)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    list_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_bp_list")

    result = await list_tool.ainvoke({"filters": "300pp+"})

    assert "筛选后只有一条成绩" in result
    assert sent == [b"single-score"]


@pytest.mark.asyncio
async def test_send_osu_bp_list_keeps_list_for_multiple_results(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    scores = [SimpleNamespace(), SimpleNamespace()]

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player", "0")

    async def fake_select(*args, **kwargs):
        return scores, scores

    async def fake_list(*args, **kwargs):
        return BytesIO(b"score-list")

    sent = []

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "select_bp_scores", fake_select)
    monkeypatch.setattr(agent_tools, "draw_pfm", fake_list)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    list_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_bp_list")

    result = await list_tool.ainvoke({"range_text": "1-2"})

    assert "bp1-2" in result
    assert sent == [b"score-list"]
