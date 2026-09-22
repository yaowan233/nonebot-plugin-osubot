from unittest.mock import AsyncMock, patch

import pytest
from httpx import Request, Response


@pytest.mark.asyncio
async def test_background_job_polls_without_resubmitting(app):
    from nonebot_plugin_osubot import api

    client = AsyncMock()
    client.post.return_value = Response(202, json={"job_id": "abc", "status": "queued"})
    client.get.side_effect = [
        Response(200, json={"job_id": "abc", "status": "running"}, request=Request("GET", "http://test/abc")),
        Response(
            200,
            json={"job_id": "abc", "status": "ready", "result": {"items": []}},
            request=Request("GET", "http://test/abc"),
        ),
    ]
    with (
        patch.object(api.network_manager, "get_client", AsyncMock(return_value=client)),
        patch.object(api.asyncio, "sleep", AsyncMock()),
    ):
        result = await api.get_recommend(992001, "mania")
    assert result.recommendations == []
    assert client.post.await_count == 1
    assert client.get.await_count == 2
    assert client.get.call_args.args[0].endswith("/recommend/personal/jobs/abc")


@pytest.mark.asyncio
async def test_failed_job_reports_error_without_restarting(app):
    from nonebot_plugin_osubot import api
    from nonebot_plugin_osubot.exceptions import NetworkError

    client = AsyncMock()
    client.post.return_value = Response(202, json={"job_id": "abc", "status": "failed", "error": "后台准备失败"})
    with (
        patch.object(api.network_manager, "get_client", AsyncMock(return_value=client)),
        pytest.raises(NetworkError, match="后台准备失败"),
    ):
        await api.get_recommend(992002, "mania")
    assert client.post.await_count == 1
    client.get.assert_not_awaited()
