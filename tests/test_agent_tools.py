import json
from datetime import datetime
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


@pytest.mark.asyncio
async def test_explicit_osu_username_uses_players_preferred_mode(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    async def fake_user(name: str):
        assert name == "miyuki"
        return {"id": 42, "username": "miyuki", "playmode": "fruits"}

    monkeypatch.setattr(agent_tools, "get_osu_user", fake_user)
    user = await agent_tools._resolve_osu_user(SimpleNamespace(), "miyuki", "osu")

    assert user.user_id == 42
    assert user.default_mode == "2"


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
    assert "工具会直接发送唯一成绩图或多成绩图片列表" in instructions
    assert "不要自行输出 Markdown 列表" in instructions


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
async def test_get_osu_scores_by_map_name_sends_image_list_when_multiple_scores_exist(monkeypatch):
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

    async def fake_draw_pfm(project, uid, scores, selected, mode, source, **kwargs):
        assert project == "map_scores"
        assert uid == 42
        assert scores == selected
        assert [score.beatmap.id for score in selected] == [101, 102]
        assert mode == "osu"
        assert source == "osu"
        return BytesIO(b"map-score-list")

    sent = []

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "search_beatmapsets", fake_search)
    monkeypatch.setattr(agent_tools, "osu_api", fake_osu_api)
    monkeypatch.setattr(agent_tools, "draw_pfm", fake_draw_pfm)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    score_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_scores_by_map_name")

    result = json.loads(await score_tool.ainvoke({"query": "Test Song"}))

    assert result["status"] == "sent"
    assert result["played_count"] == 2
    assert result["next_action"] == "finish"
    assert result["message"] == "已发送谱面成绩图片列表。"
    assert sent == [b"map-score-list"]


@pytest.mark.asyncio
async def test_send_osu_bp_list_sends_single_score_when_filter_has_one_result(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    score = _make_score()

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

    result = json.loads(await list_tool.ainvoke({"filters": "300pp+"}))

    assert "筛选后只有一条成绩" in result["message"]
    assert result["status"] == "sent"
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
    context = SimpleNamespace(user_id="12345678", request_id=None, session_id="group-1", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    list_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_bp_list")

    result = await list_tool.ainvoke({"range_text": "1-2"})

    assert "bp1-2" in result
    assert sent == [b"score-list"]


def _make_score():
    return SimpleNamespace(
        beatmap=SimpleNamespace(
            id=1,
            set_id=2,
            artist="artist",
            title="title",
            version="difficulty",
            creator="mapper",
            stars=6.5,
            bpm=180,
            total_length=120,
        ),
        statistics=SimpleNamespace(model_dump=lambda **_: {"great": 1000, "miss": 1}),
        rank="A",
        pp=300.5,
        accuracy=98.76,
        max_combo=800,
        mods=[SimpleNamespace(acronym="HD")],
        total_score=900000,
        ended_at=datetime(2026, 7, 31, 12, 0, 0),
        score_version="lazer",
    )


def _make_bp_scores(count: int, hd_start: int = 0):
    scores = []
    for i in range(count):
        score = _make_score()
        score.pp = 300.0 + i
        score.accuracy = 98.0 + (i % 10) * 0.1
        score.max_combo = 800 + i
        score.beatmap = SimpleNamespace(
            id=1000 + i,
            set_id=2000 + i,
            artist="artist",
            title=f"song-{i}",
            version="Insane",
            creator="mapper",
            stars=5.0 + (i % 5) * 0.1,
            bpm=180,
            total_length=120,
        )
        score.mods = [SimpleNamespace(acronym="HD")] if i >= hd_start else []
        score.statistics = SimpleNamespace(model_dump=lambda i=i, **kwargs: {"miss": i})
        score.rank = "S" if i % 2 == 0 else "A"
        score.ended_at = datetime(2026, 7, 31, 12, 0, 0)
        scores.append(score)
    return scores


def _make_info():
    grade_counts = SimpleNamespace(ssh=1, ss=2, sh=3, s=4, a=5)
    statistics = SimpleNamespace(
        pp=9876.5,
        global_rank=123,
        country_rank=4,
        hit_accuracy=98.76,
        play_count=1234,
        total_hits=56789,
        ranked_score=111111,
        total_score=222222,
        maximum_combo=3210,
        play_time=3600,
        grade_counts=grade_counts,
    )
    info = SimpleNamespace(
        id=42,
        username="player",
        country_code="CN",
        is_supporter=True,
        follower_count=100,
        join_date="2020-01-01",
        statistics=statistics,
    )
    return info


@pytest.mark.asyncio
async def test_send_osu_user_info_returns_structured_info(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    info = _make_info()
    sent = []

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_draw(*args, **kwargs):
        assert kwargs.get("return_info") is True
        return BytesIO(b"info-image"), info

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "draw_info", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    info_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_user_info")

    result = json.loads(await info_tool.ainvoke({"username": "player"}))

    assert result["status"] == "sent"
    assert result["player"] == "player"
    assert result["mode"] == "osu"
    assert result["info"]["username"] == "player"
    assert result["info"]["statistics"]["pp"] == 9876.5
    assert result["info"]["statistics"]["global_rank"] == 123
    assert result["info"]["statistics"]["accuracy"] == 98.76
    assert result["info"]["statistics"]["grade_counts"]["ssh"] == 1
    assert sent == [b"info-image"]


@pytest.mark.asyncio
async def test_send_osu_user_info_default_no_image_block(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    info = _make_info()

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_draw(*args, **kwargs):
        return BytesIO(b"info-image"), info

    async def fake_send(*args, **kwargs):
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "draw_info", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    info_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_user_info")

    result = await info_tool.ainvoke({"username": "player"})

    assert isinstance(result, str)
    assert "image_url" not in result


@pytest.mark.asyncio
async def test_send_osu_user_info_include_image_attaches_block(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    info = _make_info()

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_draw(*args, **kwargs):
        return BytesIO(b"info-image"), info

    async def fake_send(*args, **kwargs):
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "draw_info", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    info_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_user_info")

    result = await info_tool.ainvoke({"username": "player", "include_image_for_analysis": True})

    assert isinstance(result, list)
    assert result[0]["type"] == "text"
    assert json.loads(result[0]["text"])["status"] == "sent"
    assert result[1]["type"] == "image_url"
    assert result[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_send_osu_recent_or_pr_returns_structured_score(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    score = _make_score()
    sent = []

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_draw(*args, **kwargs):
        assert kwargs.get("return_score") is True
        return BytesIO(b"score-image"), score

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "draw_score", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    recent_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_recent_or_pr")

    result = json.loads(await recent_tool.ainvoke({"kind": "recent", "index": 3}))

    assert result["status"] == "sent"
    assert result["player"] == "player"
    assert result["scores"][0]["score"]["pp"] == 300.5
    assert result["scores"][0]["score"]["miss"] == 1
    assert result["scores"][0]["score"]["rank"] == "A"
    assert "bp_index" not in result["scores"][0]
    assert sent == [b"score-image"]


@pytest.mark.asyncio
async def test_send_osu_score_returns_structured_score(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    score = _make_score()
    sent = []

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_score_data(*args, **kwargs):
        assert kwargs.get("return_score") is True
        return BytesIO(b"score-image"), score

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "get_score_data", fake_score_data)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    score_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_score")

    result = json.loads(await score_tool.ainvoke({"beatmap_id": "114514"}))

    assert result["status"] == "sent"
    assert result["player"] == "player"
    assert result["scores"][0]["score"]["pp"] == 300.5
    assert result["scores"][0]["beatmap"]["id"] == 1
    assert "bp_index" not in result["scores"][0]
    assert sent == [b"score-image"]


@pytest.mark.asyncio
async def test_send_osu_bp_list_single_result_returns_structured_score(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    score = _make_score()
    sent = []

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player", "0")

    async def fake_select(*args, **kwargs):
        return [score], [score]

    async def fake_single(*args, **kwargs):
        return BytesIO(b"single-score"), score

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

    result = json.loads(await list_tool.ainvoke({"filters": "300pp+"}))

    assert result["status"] == "sent"
    assert result["scores"][0]["score"]["pp"] == 300.5
    assert "筛选后只有一条成绩" in result["message"]
    assert sent == [b"single-score"]


def _range_context():
    return SimpleNamespace(
        user_id="12345678",
        request_id="request-1",
        session_id="group-1",
        send_target=None,
    )


def _install_range_mocks(monkeypatch, scores, cal_identity=True):
    from nonebot_plugin_osubot import agent_tools

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_active(*args, **kwargs):
        return True

    async def fake_send(*args, **kwargs):
        raise AssertionError("纯数据工具不应发送图片")

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "is_request_active", fake_active)
    monkeypatch.setattr(agent_tools, "get_user_scores", fake_get_user_scores(scores))
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    if cal_identity:
        monkeypatch.setattr(agent_tools, "cal_score_info", lambda lazer, score, source: score)


def fake_get_user_scores(scores):
    async def _fake(*args, **kwargs):
        return list(scores)

    return _fake


@pytest.mark.asyncio
async def test_get_osu_bp_range_returns_compact_page(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    scores = _make_bp_scores(50)
    _install_range_mocks(monkeypatch, scores)
    context = _range_context()
    bundle = agent_tools.build_osu_agent_tools(context)
    range_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_bp_range")

    result = json.loads(await range_tool.ainvoke({"range_text": "1-20"}))

    assert result["status"] == "ok"
    assert result["player"] == "player"
    assert result["mode"] == "osu"
    assert result["total"] == 50
    assert result["range"] == [1, 20]
    assert result["has_more"] is True
    assert result["next_start"] == 21
    assert len(result["scores"]) == 20
    first = result["scores"][0]
    assert first["index"] == 1
    assert first["title"] == "song-0"
    assert first["pp"] == 300.0
    assert first["accuracy"] == 98.0
    assert first["combo"] == 800
    assert first["mods"] == ["HD"]
    assert len(json.dumps(result, ensure_ascii=False)) < 5000


@pytest.mark.asyncio
async def test_get_osu_bp_range_rejects_wide_range(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    scores = _make_bp_scores(50)
    _install_range_mocks(monkeypatch, scores)
    context = _range_context()
    bundle = agent_tools.build_osu_agent_tools(context)
    range_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_bp_range")

    result = json.loads(await range_tool.ainvoke({"range_text": "1-30"}))

    assert result["status"] == "failed"
    assert "最多读取 20 条" in result["message"]


@pytest.mark.asyncio
async def test_get_osu_bp_range_last_page_has_no_more(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    scores = _make_bp_scores(50)
    _install_range_mocks(monkeypatch, scores)
    context = _range_context()
    bundle = agent_tools.build_osu_agent_tools(context)
    range_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_bp_range")

    result = json.loads(await range_tool.ainvoke({"range_text": "41-60"}))

    assert result["status"] == "ok"
    assert result["range"] == [41, 50]
    assert result["has_more"] is False
    assert "next_start" not in result
    assert len(result["scores"]) == 10


@pytest.mark.asyncio
async def test_get_osu_bp_range_caches_bp_list_across_pages(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    scores = _make_bp_scores(50)
    calls = {"fetch": 0}

    async def counting_get(*args, **kwargs):
        calls["fetch"] += 1
        return list(scores)

    _install_range_mocks(monkeypatch, scores)
    monkeypatch.setattr(agent_tools, "get_user_scores", counting_get)
    context = _range_context()
    bundle = agent_tools.build_osu_agent_tools(context)
    range_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_bp_range")

    first = json.loads(await range_tool.ainvoke({"range_text": "1-20"}))
    second = json.loads(await range_tool.ainvoke({"range_text": "21-40"}))

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert calls == {"fetch": 1}


@pytest.mark.asyncio
async def test_get_osu_bp_range_mods_filter(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    scores = _make_bp_scores(50, hd_start=3)
    _install_range_mocks(monkeypatch, scores)
    context = _range_context()
    bundle = agent_tools.build_osu_agent_tools(context)
    range_tool = next(tool for tool in bundle.tools if tool.name == "get_osu_bp_range")

    result = json.loads(await range_tool.ainvoke({"range_text": "1-20", "mods": "HD"}))

    assert result["status"] == "ok"
    assert result["total"] == 47
    assert len(result["scores"]) == 20
    assert all(item["mods"] == ["HD"] for item in result["scores"])
    assert result["scores"][0]["title"] == "song-3"


@pytest.mark.asyncio
async def test_send_osu_bp_list_dedups_repeat_list_image(monkeypatch):
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

    async def fake_active(*args, **kwargs):
        return True

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "select_bp_scores", fake_select)
    monkeypatch.setattr(agent_tools, "draw_pfm", fake_list)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    monkeypatch.setattr(agent_tools, "is_request_active", fake_active)
    context = SimpleNamespace(user_id="12345678", request_id="request-1", session_id="group-1", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    list_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_bp_list")

    first = await list_tool.ainvoke({"range_text": "1-2"})
    second = await list_tool.ainvoke({"range_text": "1-2"})

    assert "已发送" in first
    assert "不再重复发送" in second
    assert sent == [b"score-list"]


@pytest.mark.asyncio
async def test_instructions_contain_bp_analysis_recipe():
    from nonebot_plugin_osubot.agent_tools import build_osu_agent_tools

    context = SimpleNamespace(user_id="12345678")
    bundle = build_osu_agent_tools(context)
    instructions = "\n".join(bundle.instructions)
    tool_names = {tool.name for tool in bundle.tools}

    assert "get_osu_bp_range" in tool_names
    assert "两段式" in instructions
    assert "send_osu_bp_list 发送 BP 列表图" in instructions
    assert "next_start 续读" in instructions
    assert "读到 has_more=false" in instructions
    assert "范围宽度必须 ≤20" in instructions
    assert "最多传 10 个 BP 序号" in instructions


def _history_points(count: int = 25):
    return [(3000.0 + i * 20.0, f"2026-01-{(i % 28) + 1:02d}", 1000 - i * 5) for i in range(count)]


class _FakeScalars:
    def all(self):
        return []


class _FakeSession:
    async def scalars(self, *args, **kwargs):
        return _FakeScalars()


class _FakeSessionCM:
    async def __aenter__(self):
        return _FakeSession()

    async def __aexit__(self, *args):
        return False


def _install_history_mocks(monkeypatch, points, include_image=False):
    from nonebot_plugin_osubot import agent_tools

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_merge(*args, **kwargs):
        return list(points), True

    async def fake_draw(*args, **kwargs):
        return BytesIO(b"history-image")

    sent = []

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "get_session", lambda: _FakeSessionCM())
    monkeypatch.setattr(agent_tools, "merge_osutrack_history", fake_merge)
    monkeypatch.setattr(agent_tools, "draw_history_plot", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    return sent


@pytest.mark.asyncio
async def test_send_osu_history_returns_structured_data(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    points = _history_points(25)
    sent = _install_history_mocks(monkeypatch, points)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    history_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_history")

    raw = await history_tool.ainvoke({"day": 0})
    result = json.loads(raw)

    assert isinstance(raw, str)
    assert result["status"] == "sent"
    assert result["player"] == "player"
    assert result["mode"] == "osu"
    history = result["history"]
    assert history["points"] == 25
    assert history["span"] == {"from": points[0][1], "to": points[-1][1]}
    assert history["pp"]["first"] == 3000.0
    assert history["pp"]["last"] == 3480.0
    assert history["pp"]["change"] == 480.0
    assert history["rank"]["first"] == 1000
    assert history["rank"]["last"] == 880
    assert history["rank"]["best"] == 880
    assert len(history["recent"]) == 20
    assert sent == [b"history-image"]


@pytest.mark.asyncio
async def test_send_osu_history_include_image_attaches_block(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    points = _history_points(5)
    sent = _install_history_mocks(monkeypatch, points)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    history_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_history")

    raw = await history_tool.ainvoke({"day": 0, "include_image_for_analysis": True})

    assert isinstance(raw, list)
    assert raw[0]["type"] == "text"
    assert json.loads(raw[0]["text"])["status"] == "sent"
    assert raw[1]["type"] == "image_url"
    assert raw[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert sent == [b"history-image"]


@pytest.mark.asyncio
async def test_send_osu_recommend_returns_structured_data(monkeypatch):
    from nonebot_plugin_osubot import agent_tools
    from nonebot_plugin_osubot.schema.alphaosu import RecommendData, RecommendItem, RecommendSection

    recommend_data = RecommendData(
        player_id=42,
        mode="osu",
        target="mixed",
        recommendations=[
            RecommendItem(
                map_id=101,
                mod=0,
                mod_str="NM",
                stars=5.2,
                pred_pp=320.5,
                pred_acc=98.3,
                final_score=100,
                title="artist - song [Insane]",
                beatmapset_id=10,
                url="https://osu.ppy.sh/b/101",
            ),
            RecommendItem(
                map_id=102,
                mod=8,
                mod_str="HD",
                stars=5.8,
                pred_pp=350.0,
                pred_acc=97.5,
                final_score=100,
                title="artist2 - song2 [Another]",
                beatmapset_id=11,
                url=None,
            ),
        ],
        sections=[
            RecommendSection(
                key="overall",
                title="综合推荐",
                items=[
                    RecommendItem(
                        map_id=i,
                        mod=0,
                        mod_str="NM",
                        stars=4.0,
                        pred_pp=200.0,
                        pred_acc=99.0,
                        final_score=100,
                        title=f"artist - song{i} [Hard]",
                        beatmapset_id=i,
                        url=None,
                    )
                    for i in range(103, 107)
                ],
            ),
        ],
    )
    sent = []

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_recommend(*args, **kwargs):
        return recommend_data

    async def fake_draw(*args, **kwargs):
        return BytesIO(b"recommend-image")

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "get_recommend", fake_recommend)
    monkeypatch.setattr(agent_tools, "draw_recommend", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    recommend_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_recommend")

    raw = await recommend_tool.ainvoke({"target": "mixed"})
    result = json.loads(raw)

    assert isinstance(raw, str)
    assert result["status"] == "sent"
    assert result["player"] == "player"
    assert result["mode"] == "osu"
    recommend = result["recommend"]
    assert recommend["target"] == "mixed"
    assert len(recommend["recommendations"]) == 2
    assert recommend["recommendations"][0]["title"] == "artist - song [Insane]"
    assert recommend["recommendations"][0]["pred_pp"] == 320.5
    assert recommend["recommendations"][0]["mod"] == "NM"
    assert recommend["sections"][0]["title"] == "综合推荐"
    assert recommend["sections"][0]["count"] == 4
    assert len(recommend["sections"][0]["top"]) == 3
    assert sent == [b"recommend-image"]


@pytest.mark.asyncio
async def test_send_osu_bp_analysis_returns_structured_data(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    bpa_data = {
        "stats": {
            "weighted_pp": 1000.0,
            "total_pp": 1200.0,
            "bp_count": 50,
            "avg_acc": 98.5,
            "avg_stars": 6.2,
            "avg_bpm": 180.0,
            "top_mod": "HD",
            "top_mapper": "mapper",
        },
        "star_scatter": [
            {"name": "XH", "color": "#c7eaf5", "data": [[6.0, 300.0], [6.5, 320.0]]},
            {"name": "A", "color": "#84d61c", "data": [[7.0, 250.0]]},
            {"name": "D", "color": "#f55757", "data": []},
        ],
        "mod_pp_ls": [{"name": "HD", "value": 500.0}, {"name": "DT", "value": 300.0}],
        "mapper_pp_ls": [{"name": "mapper", "value": 800.0}],
        "pp_ls": [],
        "length_ls": [],
        "acc_ls": [],
        "bpm_ls": [],
        "date_ls": [],
    }
    sent = []

    async def fake_resolve(*args, **kwargs):
        return agent_tools.ResolvedOsuUser(42, "player")

    async def fake_scores(*args, **kwargs):
        return [SimpleNamespace(mods=[SimpleNamespace(acronym="HD")], beatmap=None)]

    async def fake_bpa(*args, **kwargs):
        return bpa_data

    async def fake_draw(*args, **kwargs):
        return BytesIO(b"bpa-image")

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "_resolve_osu_user", fake_resolve)
    monkeypatch.setattr(agent_tools, "get_user_scores", fake_scores)
    monkeypatch.setattr(agent_tools, "cal_score_info", lambda is_lazer, score: score)
    monkeypatch.setattr(agent_tools, "build_bpa_data", fake_bpa)
    monkeypatch.setattr(agent_tools, "draw_bpa_plot", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    bpa_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_bp_analysis")

    raw = await bpa_tool.ainvoke({})
    result = json.loads(raw)

    assert isinstance(raw, str)
    assert result["status"] == "sent"
    assert result["player"] == "player"
    assert result["mode"] == "osu"
    bpa = result["bpa"]
    assert bpa["stats"]["weighted_pp"] == 1000.0
    assert bpa["stats"]["top_mod"] == "HD"
    ranks = bpa["rank_distribution"]
    assert [item["rank"] for item in ranks] == ["XH", "A"]
    assert ranks[0]["count"] == 2
    assert ranks[0]["avg_stars"] == 6.25
    assert ranks[0]["avg_pp"] == 310.0
    assert bpa["mod_pp_contribution"] == [{"name": "HD", "value": 500.0}, {"name": "DT", "value": 300.0}]
    assert bpa["top_mappers"] == [{"name": "mapper", "value": 800.0}]
    assert sent == [b"bpa-image"]


def _match_history_data():
    return {
        "match_id": "12345",
        "title": "Lobby vs Match",
        "team_type": "team-vs",
        "is_team": True,
        "red_name": "红队",
        "blue_name": "蓝队",
        "red_wins": 2,
        "blue_wins": 1,
        "game_count": 3,
        "player_count": 6,
        "team_size": 3,
        "duration": 2400,
        "time_range": "2026/01/01 12:00—13:00",
        "complete": True,
        "games": [
            {
                "index": 1,
                "map_id": 101,
                "title": "song",
                "version": "Insane",
                "creator": "mapper",
                "cover": "",
                "stars": 5.5,
                "winner": "red",
                "red_score": 300,
                "blue_score": 200,
                "players": [
                    {
                        "user_id": 1,
                        "name": "alice",
                        "avatar": "",
                        "team": "red",
                        "score": 100,
                        "accuracy": 98.5,
                        "combo": 500,
                        "mods": ["HD"],
                    },
                    {
                        "user_id": 2,
                        "name": "bob",
                        "avatar": "",
                        "team": "blue",
                        "score": 90,
                        "accuracy": 97.0,
                        "combo": 400,
                        "mods": [],
                    },
                ],
                "red_players": [],
                "blue_players": [],
            }
        ],
    }


def _match_rating_data():
    return {
        "match_id": "12345",
        "title": "Lobby vs Match",
        "time_range": "2026/01/01 12:00—13:00",
        "team_type": "team-vs",
        "algorithm": "OSUPLUS",
        "game_count": 3,
        "player_count": 2,
        "players": [
            {
                "rank": 1,
                "name": "alice",
                "team": "red",
                "rating": 2.34,
                "total_score": 5000,
                "average_score": 1666.67,
                "wins": 2,
                "losses": 1,
                "played": 3,
                "win_rate": 0.6667,
                "record_text": "2W—1L · 66.7%",
            },
            {
                "rank": 2,
                "name": "bob",
                "team": "blue",
                "rating": 1.2,
                "total_score": 3000,
                "average_score": 1000.0,
                "wins": 1,
                "losses": 2,
                "played": 3,
                "win_rate": 0.3333,
                "record_text": "1W—2L · 33.3%",
            },
        ],
        "mvp": {
            "rank": 1,
            "name": "alice",
            "team": "red",
            "rating": 2.34,
            "total_score": 5000,
            "average_score": 1666.67,
            "wins": 2,
            "losses": 1,
            "played": 3,
            "win_rate": 0.6667,
            "record_text": "2W—1L · 66.7%",
        },
        "max_top1_count": 0,
        "max_total_score": 5000,
        "average_rating": 1.77,
        "red_name": "红队",
        "blue_name": "蓝队",
        "red_wins": 2,
        "blue_wins": 1,
        "red_players": [],
        "blue_players": [],
        "team_size": 3,
    }


@pytest.mark.asyncio
async def test_send_osu_match_history_returns_structured_data(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    sent = []

    async def fake_draw(*args, **kwargs):
        assert kwargs.get("return_data") is True
        return BytesIO(b"match-image"), _match_history_data()

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "draw_match_history", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    match_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_match_history")

    raw = await match_tool.ainvoke({"match_id": "12345"})
    result = json.loads(raw)

    assert isinstance(raw, str)
    assert result["status"] == "sent"
    match = result["match"]
    assert match["title"] == "Lobby vs Match"
    assert match["red_wins"] == 2
    assert match["blue_wins"] == 1
    assert match["game_count"] == 3
    assert match["team_size"] == 3
    game = match["games"][0]
    assert game["map"] == "song [Insane]"
    assert game["winner"] == "red"
    assert game["red_score"] == 300
    assert game["mvp"]["name"] == "alice"
    assert game["mvp"]["accuracy"] == 98.5
    assert game["mvp"]["mods"] == ["HD"]
    assert sent == [b"match-image"]


@pytest.mark.asyncio
async def test_send_osu_match_rating_returns_structured_data(monkeypatch):
    from nonebot_plugin_osubot import agent_tools

    sent = []

    async def fake_draw(*args, **kwargs):
        assert kwargs.get("return_data") is True
        return BytesIO(b"rating-image"), _match_rating_data()

    async def fake_send(ctx, image):
        sent.append(image.getvalue())
        return "已发送图片"

    monkeypatch.setattr(agent_tools, "draw_rating", fake_draw)
    monkeypatch.setattr(agent_tools, "_send_image", fake_send)
    context = SimpleNamespace(user_id="12345678", send_target=None)
    bundle = agent_tools.build_osu_agent_tools(context)
    rating_tool = next(tool for tool in bundle.tools if tool.name == "send_osu_match_rating")

    raw = await rating_tool.ainvoke({"match_id": "12345"})
    result = json.loads(raw)

    assert isinstance(raw, str)
    assert result["status"] == "sent"
    rating = result["rating"]
    assert rating["algorithm"] == "OSUPLUS"
    assert rating["average_rating"] == 1.77
    assert rating["red_wins"] == 2
    assert rating["mvp"]["name"] == "alice"
    assert rating["mvp"]["rating"] == 2.34
    assert rating["mvp"]["win_rate"] == 66.67
    assert len(rating["players"]) == 2
    assert rating["players"][0]["wins"] == 2
    assert rating["players"][0]["losses"] == 1
    assert "top1_rate" not in rating["players"][0]
    assert sent == [b"rating-image"]


def test_match_player_summary_includes_top1_rate_for_head_to_head():
    from nonebot_plugin_osubot.agent_tools import _match_player_summary

    player = {
        "rank": 1,
        "name": "carol",
        "team": "none",
        "rating": 3.0,
        "total_score": 1000,
        "average_score": 500,
        "played": 4,
        "top1_count": 3,
        "top1_rate": 0.75,
    }
    summary = _match_player_summary(player)

    assert summary["top1_rate"] == 75.0
    assert "wins" not in summary
    assert "win_rate" not in summary
