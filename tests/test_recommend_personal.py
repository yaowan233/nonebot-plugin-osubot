import pytest
from httpx import Response
from unittest.mock import AsyncMock, patch


@pytest.mark.parametrize("mode", ["osu", "fruits", "mania", "taiko"])
def test_personal_contract(mode):
    from nonebot_plugin_osubot.recommendation import personal_request

    body = personal_request(42, mode, "mixed", 500, 24)
    assert body["target"] == "balanced"
    assert body["include_converts"] == (mode in {"taiko", "fruits"})
    assert body["exclude_recorded_plays"]
    assert "key_counts" not in body
    assert personal_request(42, mode, "peak", 500, 24)["target"] == "peak"


@pytest.mark.parametrize("mode", ["fruits", "mania", "taiko"])
def test_goal_pp_and_gain_are_not_model_prediction(mode):
    from nonebot_plugin_osubot.recommendation import prediction_display

    goal_key = "practice_target" if mode == "fruits" else "accuracy_target"
    item = {"pred_pp": 100, "pred_acc": 94, "key_count": 7}
    item[goal_key] = {"pp": 300, "accuracy": 98, "weighted_gain": 12.34, "misses": 0}
    result = prediction_display(item, mode)
    assert result["pred_pp"] == 300
    assert result["pred_acc"] == 98
    assert result["weighted_gain"] == 12.34
    assert ("7K" if mode == "mania" else "FC") in result["evidence_line"]


@pytest.mark.parametrize("mode", ["osu", "fruits", "mania", "taiko"])
@pytest.mark.parametrize(("observed", "expected"), [(6, "4/6"), (None, "4"), (3, "4"), (True, "4"), ("6", "4")])
def test_goal_support_counts_unique_players(mode, observed, expected):
    from nonebot_plugin_osubot.recommendation import prediction_display

    goal_key = "practice_target" if mode == "fruits" else "accuracy_target"
    evidence_key = "fc_evidence" if mode == "fruits" else "accuracy_evidence"
    item = {
        goal_key: {"pp": 300, "accuracy": 98, "weighted_gain": 12},
        evidence_key: {
            "observed_players": observed,
            "references": [{"player_id": player_id} for player_id in [1, 2, 3, 4, 4]],
        },
    }
    result = prediction_display(item, mode)
    assert result["evidence_line"].endswith(f"{expected} 人支持目标")
    assert result["pred_pp"] == 300
    assert result["pred_acc"] == 98


def test_own_map_references_are_not_reported_as_players():
    from nonebot_plugin_osubot.recommendation import prediction_display

    result = prediction_display(
        {
            "practice_target": {"pp": 300, "accuracy": 98},
            "fc_evidence": {"references": [{"map_id": 1}, {"map_id": 2}]},
        },
        "fruits",
    )
    assert result["evidence_line"].endswith("2 条参考实绩")


def test_std_prediction_and_zero_gain():
    from nonebot_plugin_osubot.recommendation import prediction_display

    result = prediction_display(
        {
            "pred_pp": 300,
            "pred_acc": 98,
            "predicted_weighted_snapshot_gain": 0,
            "performance_prediction_source": "osu-joint-model",
            "expected_miss": 1.2,
            "pred_combo": 1234,
        },
        "osu",
    )
    assert result["weighted_gain"] == 0
    assert "1.2 Miss" in result["evidence_line"]
    assert "1234x" in result["evidence_line"]
    assert prediction_display({}, "osu")["weighted_gain"] is None


@pytest.mark.parametrize("mode", ["osu", "fruits", "mania", "taiko"])
def test_prediction_without_practice_target_has_explanation(mode):
    from nonebot_plugin_osubot.recommendation import prediction_display

    result = prediction_display({"pred_pp": 123, "pred_acc": 97.5, "key_count": 7}, mode)
    assert result["evidence_line"]
    assert "预测" in result["evidence_line"]
    assert "无练习目标" in result["evidence_line"]
    assert result["pred_pp"] == 123
    assert result["pred_acc"] == 97.5
    assert result["weighted_gain"] is None
    if mode == "mania":
        assert "7K" in result["evidence_line"]


def test_catch_prediction_is_not_an_fc_promise():
    from nonebot_plugin_osubot.recommendation import prediction_display

    result = prediction_display({"expected_miss": 0, "pred_combo": 1000}, "fruits")
    assert "0.0 Miss" in result["evidence_line"]
    assert "1000x" in result["evidence_line"]
    assert "预测" in result["evidence_line"]
    assert "FC" not in result["evidence_line"]


def test_unknown_gain_is_not_drawn_as_zero():
    from nonebot_plugin_osubot.draw.recommend_svg import build_recommend_svg
    from test_native_card_renderers import _recommend_payload

    payload = _recommend_payload()
    svg, _ = build_recommend_svg(payload)
    assert "收益未知" in svg
    assert "+0.00 pp" not in svg


@pytest.mark.asyncio
async def test_timeout_is_not_retried_and_auth_is_sent(app):
    from nonebot_plugin_osubot import api
    from nonebot_plugin_osubot.exceptions import NetworkError

    client = AsyncMock()
    client.post.return_value = Response(504)
    with (
        patch.object(api.network_manager, "get_client", AsyncMock(return_value=client)),
        patch.object(api.plugin_config, "osu_recommend_api_token", "test-token"),
        pytest.raises(NetworkError, match="准备超时"),
    ):
        await api.get_recommend(42, 3)
    assert client.post.await_count == 1
    assert client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
async def test_new_fields_reach_image_renderer(app):
    import importlib
    from nonebot_plugin_osubot.schema.alphaosu import RecommendData

    drawing = importlib.import_module("nonebot_plugin_osubot.draw.recommend")
    data = RecommendData(
        mode="mania",
        target="mixed",
        recommendations=[
            {
                "map_id": 1,
                "mod": 0,
                "mod_str": "NM",
                "stars": 5,
                "pred_pp": 300,
                "pred_acc": 98,
                "final_score": 12,
                "title": "Test",
                "weighted_gain": 12.34,
                "evidence_line": "7K · ACC 目标",
            }
        ],
    )
    with (
        patch.object(drawing, "_cover_data_uri", AsyncMock(return_value=None)),
        patch.object(drawing, "_player_avatar", AsyncMock(return_value="")),
        patch.object(drawing, "render_recommend_svg", AsyncMock(return_value=b"image")) as render,
    ):
        assert await drawing.draw_recommend(data, "player", "") == b"image"
    payload = render.call_args.args[0]
    assert payload["flat"][0]["weighted_gain"] == 12.34
    assert payload["flat"][0]["evidence_line"] == "7K · ACC 目标"
    assert payload["section_titles"] == ["综合推荐"]
