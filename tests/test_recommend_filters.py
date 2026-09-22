import pytest
from httpx import Response
from unittest.mock import AsyncMock, patch

def test_mania_filters_are_preserved_without_changing_defaults():
    from nonebot_plugin_osubot.recommendation import personal_request
    from nonebot_plugin_osubot.recommendation_filters import RecommendationFilters

    filters = RecommendationFilters(key_counts=[4, 7], min_stars=5, max_stars=6, max_length=180,
                                    feature_ranges={"ln_ratio": {"min": 0.2, "max": 0.5}},
                                    exclude_recorded_plays=False, mods=["NM", "HT"], result_limit=24)
    body = personal_request(42, "mania", "mixed", 500, 10, filters)
    assert body["key_counts"] == [4, 7]
    assert body["feature_ranges"] == {"ln_ratio": {"min": 0.2, "max": 0.5}}
    assert body["target"] == "balanced"
    assert body["result_limit"] == 24
    assert body["candidate_limit"] == 500
    assert not body["exclude_recorded_plays"]
    assert body["mods"] == ["NM", "HT"]
    assert body["max_length"] == 180


def test_ctb_converts_can_be_explicitly_excluded():
    from nonebot_plugin_osubot.recommendation import personal_request

    assert personal_request(42, "fruits", "mixed", 500, 20)["include_converts"] is True
    body = personal_request(42, "fruits", "mixed", 500, 20, {"include_converts": False})
    assert body["include_converts"] is False


@pytest.mark.parametrize(("mode", "name"), [
    ("osu", "slider_ratio"), ("taiko", "rim_ratio"), ("fruits", "edge_ratio"), ("mania", "chord_ratio"),
])
def test_mode_feature_ranges(mode, name):
    from nonebot_plugin_osubot.recommendation import personal_request

    body = personal_request(42, mode, "style", 500, 10, {"feature_ranges": {name: {"max": 0.3}}})
    assert body["feature_ranges"] == {name: {"max": 0.3}}


@pytest.mark.parametrize(("mode", "filters"), [
    ("osu", {"key_counts": [4]}),
    ("mania", {"key_counts": [3]}),
    ("mania", {"key_counts": [4.5]}),
    ("mania", {"key_counts": [4, 4]}),
    ("mania", {"feature_ranges": {"ln_ratio": {"max": 30}}}),
    ("mania", {"feature_ranges": {"ln_ratio": {"min": 0.5, "max": 0.2}}}),
    ("mania", {"feature_ranges": {"ln_ratio": {}}}),
    ("osu", {"feature_ranges": {"ln_ratio": {"max": 0.5}}}),
    ("osu", {"min_stars": 7, "max_stars": 6}),
    ("osu", {"min_bpm": 200, "max_bpm": 100}),
    ("osu", {"max_length": 0}),
    ("osu", {"mods": []}),
    ("osu", {"mods": ["DTHR"]}),
    ("osu", {"mods": ["DT", "DT"]}),
    ("osu", {"result_limit": 51}),
    ("osu", {"min_pp": 300}),
    ("osu", {"max_stars": float("nan")}),
])
def test_invalid_filters_are_rejected_instead_of_ignored(mode, filters):
    from nonebot_plugin_osubot.recommendation import personal_request

    with pytest.raises(ValueError, match=".+"):
        personal_request(42, mode, "mixed", 500, 10, filters)


@pytest.mark.asyncio
async def test_api_posts_and_echoes_filters(app):
    from nonebot_plugin_osubot import api

    client = AsyncMock()
    client.post.return_value = Response(200, json={"items": []})
    with patch.object(api.network_manager, "get_client", AsyncMock(return_value=client)):
        result = await api.get_recommend(42, "taiko", filters={
            "min_bpm": 150, "max_bpm": 200, "include_converts": False, "mods": ["DTHR"]})
    body = client.post.call_args.kwargs["json"]
    assert body["min_bpm"] == 150
    assert body["max_bpm"] == 200
    assert body["mods"] == ["DTHR"]
    assert body["include_converts"] is False
    assert result.applied_filters == body


@pytest.mark.asyncio
async def test_invalid_filters_do_not_contact_server(app):
    from nonebot_plugin_osubot import api

    with patch.object(api, "_request_recommend", AsyncMock()) as request:
        with pytest.raises(ValueError, match="键数"):
            await api.get_recommend(42, "osu", filters={"key_counts": [4]})
    request.assert_not_awaited()
