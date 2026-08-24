import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def api_module(after_nonebot_init):
    return importlib.import_module("nonebot_plugin_osubot.api")


@pytest.fixture
def audio_module(after_nonebot_init):
    return importlib.import_module("nonebot_plugin_osubot.matcher.audio")


@pytest.mark.asyncio
async def test_preview_audio_uses_map_specific_osu_direct_endpoint(api_module):
    response = SimpleNamespace(status_code=200, content=b"audio" * 1024)

    with patch.object(api_module, "get_first_response", new=AsyncMock(return_value=response)) as request:
        assert await api_module.get_preview_audio(123) == response.content

    request.assert_awaited_once_with(
        ["https://osu.direct/api/media/preview/123"],
        timeout=15.0,
    )


@pytest.mark.asyncio
async def test_beatmapset_preview_uses_only_set_id_mirrors(api_module):
    response = SimpleNamespace(status_code=200, content=b"audio" * 1024)

    with patch.object(api_module, "get_first_response", new=AsyncMock(return_value=response)) as request:
        assert await api_module.get_beatmapset_preview_audio(456) == response.content

    request.assert_awaited_once_with(
        [
            "https://cdn.sayobot.cn:25225/preview/456.mp3",
            "https://a.sayobot.cn/preview/456.mp3",
        ],
        timeout=15.0,
    )


@pytest.mark.asyncio
async def test_fetch_voice_uses_bid_specific_preview(audio_module):
    with (
        patch.object(audio_module, "_bid_to_sid", new=AsyncMock(return_value=456)),
        patch.object(audio_module, "get_preview_audio", new=AsyncMock(return_value=b"audio")) as preview,
        patch.object(audio_module, "get_beatmapset_preview_audio", new=AsyncMock()) as set_preview,
    ):
        assert await audio_module._fetch_voice(123) == b"audio"

    preview.assert_awaited_once_with(123)
    set_preview.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_voice_uses_set_preview_only_when_id_is_not_a_bid(audio_module):
    with (
        patch.object(audio_module, "_bid_to_sid", new=AsyncMock(return_value=None)),
        patch.object(audio_module, "get_preview_audio", new=AsyncMock()) as preview,
        patch.object(audio_module, "get_beatmapset_preview_audio", new=AsyncMock(return_value=b"audio")) as set_preview,
    ):
        assert await audio_module._fetch_voice(456) == b"audio"

    preview.assert_not_awaited()
    set_preview.assert_awaited_once_with(456)


@pytest.mark.asyncio
async def test_audio_command_sends_only_the_voice(audio_module):
    message = MagicMock()
    message.finish = AsyncMock()

    with (
        patch.object(audio_module, "_fetch_voice", new=AsyncMock(return_value=b"audio")),
        patch.object(audio_module.UniMessage, "text") as text,
        patch.object(audio_module.UniMessage, "voice", return_value=message) as voice,
    ):
        await audio_module._audio(MagicMock(), {"target": "123"})

    text.assert_not_called()
    voice.assert_called_once_with(raw=b"audio")
    message.finish.assert_awaited_once_with()
