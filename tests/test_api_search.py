from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_search_beatmapsets_uses_official_free_text_search(monkeypatch):
    from nonebot_plugin_osubot import api

    api.beatmap_search_cache.clear()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"beatmapsets": [{"id": 123}]}
    request = AsyncMock(return_value=response)
    headers = AsyncMock(return_value={"Authorization": "Bearer token"})
    monkeypatch.setattr(api, "safe_async_get", request)
    monkeypatch.setattr(api, "get_headers", headers)

    result = await api.search_beatmapsets("Freedom Dive")

    assert result == [{"id": 123}]
    called_url = request.await_args.args[0]
    assert called_url.startswith("https://osu.ppy.sh/api/v2/beatmapsets/search?")
    assert "q=Freedom+Dive" in called_url
    assert "s=any" in called_url


@pytest.mark.asyncio
async def test_search_beatmapsets_caches_same_query(monkeypatch):
    from nonebot_plugin_osubot import api

    api.beatmap_search_cache.clear()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"beatmapsets": [{"id": 123}]}
    request = AsyncMock(return_value=response)
    monkeypatch.setattr(api, "safe_async_get", request)
    monkeypatch.setattr(api, "get_headers", AsyncMock(return_value={}))

    await api.search_beatmapsets("Freedom Dive")
    await api.search_beatmapsets("freedom dive")

    request.assert_awaited_once()
