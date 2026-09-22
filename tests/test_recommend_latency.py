import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response


@pytest.mark.asyncio
async def test_repeated_identical_recommendations_do_not_recompute(app):
    from nonebot_plugin_osubot import api

    response = Response(200, json={"items": [{
        "beatmap_id": 1, "beatmapset_id": 2, "mods": "NM", "title": "Test", "version": "Test",
        "pred_pp": 200, "pred_acc": 98, "ranking_score": 1, "stars": 5,
    }]})
    with patch.object(api, "_request_recommend", AsyncMock(return_value=response)) as request:
        await api.get_recommend(991001, "mania")
        await api.get_recommend(991001, "mania")
    assert request.await_count == 1


@pytest.mark.asyncio
async def test_cache_expiry_copy_isolation_and_failure(app):
    from nonebot_plugin_osubot.recommendation_response_cache import RecommendationResponseCache

    cache = RecommendationResponseCache(capacity=1)
    factory = AsyncMock(return_value=SimpleNamespace(recommendations=[{"map": 1}]))
    first = await cache.get("one", factory, 120)
    first.recommendations.clear()
    assert (await cache.get("one", factory, 120)).recommendations
    assert factory.await_count == 1
    cache.values["one"] = (0, factory.return_value)
    await cache.get("one", factory, 120)
    assert factory.await_count == 2
    await cache.get("two", factory, 120)
    assert list(cache.values) == ["two"]
    failure = AsyncMock(side_effect=RuntimeError("failed"))
    with pytest.raises(RuntimeError, match="failed"):
        await cache.get("bad", failure, 120)
    assert "bad" not in cache.pending
    assert "bad" not in cache.values


@pytest.mark.asyncio
async def test_cancelling_one_waiter_preserves_shared_computation(app):
    from nonebot_plugin_osubot.recommendation_response_cache import RecommendationResponseCache

    cache = RecommendationResponseCache()
    started, release = asyncio.Event(), asyncio.Event()

    async def compute():
        started.set()
        await release.wait()
        return SimpleNamespace(recommendations=[1])

    first = asyncio.create_task(cache.get("key", compute, 120))
    await started.wait()
    second = asyncio.create_task(cache.get("key", compute, 120))
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    assert (await second).recommendations == [1]
    assert not cache.pending


@pytest.mark.asyncio
async def test_slow_assets_do_not_hold_up_render(app):
    import importlib
    from nonebot_plugin_osubot.schema.alphaosu import RecommendData

    drawing = importlib.import_module("nonebot_plugin_osubot.draw.recommend")

    async def slow(*args):
        await asyncio.sleep(30)

    data = RecommendData(recommendations=[{
        "map_id": 1, "mod": 0, "mod_str": "NM", "stars": 5, "pred_pp": 200,
        "pred_acc": 98, "final_score": 1, "title": "Test", "beatmapset_id": 1,
    }])
    with (
        patch.object(drawing.plugin_config, "osu_recommend_asset_timeout", 0.01),
        patch.object(drawing, "_cover_data_uri", slow),
        patch.object(drawing, "_player_avatar", slow),
        patch.object(drawing, "render_recommend_svg", AsyncMock(return_value=b"rendered")),
    ):
        assert await asyncio.wait_for(drawing.draw_recommend(data, "test", ""), 1) == b"rendered"


@pytest.mark.asyncio
async def test_changed_filters_do_not_reuse_old_results(app):
    from nonebot_plugin_osubot import api

    response = Response(200, json={"items": [{
        "beatmap_id": 1, "beatmapset_id": 2, "mods": "NM", "title": "Test", "version": "Test",
        "pred_pp": 200, "pred_acc": 98, "ranking_score": 1, "stars": 5,
    }]})
    with patch.object(api, "_request_recommend", AsyncMock(return_value=response)) as request:
        await api.get_recommend(991003, "mania", filters={"key_counts": [4]})
        await api.get_recommend(991003, "mania", filters={"key_counts": [7]})
    assert request.await_count == 2


@pytest.mark.asyncio
async def test_transport_timeout_is_not_retried(app):
    from httpx import ReadTimeout
    from nonebot_plugin_osubot import api
    from nonebot_plugin_osubot.exceptions import NetworkError

    client = AsyncMock()
    client.post.side_effect = ReadTimeout("timed out")
    with (
        patch.object(api.network_manager, "get_client", AsyncMock(return_value=client)),
        pytest.raises(NetworkError, match="等待超时"),
    ):
        await api.get_recommend(991004, "mania")
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_parallel_identical_recommendations_share_work(app):
    from nonebot_plugin_osubot import api

    async def compute(*args, **kwargs):
        await asyncio.sleep(0.01)
        return Response(200, json={"items": []})

    with patch.object(api, "_request_recommend", AsyncMock(side_effect=compute)) as request:
        await asyncio.gather(*(api.get_recommend(991002, "mania") for _index in range(5)))
    assert request.await_count == 1
