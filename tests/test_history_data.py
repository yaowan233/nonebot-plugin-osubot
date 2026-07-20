from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_osutrack_history_is_deduplicated_by_day():
    from nonebot_plugin_osubot import history_data

    response = MagicMock(status_code=200)
    response.json.return_value = [
        {"timestamp": "2026-07-01T01:00:00.000Z", "pp_raw": 1000, "pp_rank": 10000},
        {"timestamp": "2026-07-01T20:00:00.000Z", "pp_raw": 1010, "pp_rank": 9900},
        {"timestamp": "2026-07-02T12:00:00.000Z", "pp_raw": 1020, "pp_rank": 9800},
    ]
    history_data.clear_history_cache()
    with patch.object(history_data.plugin_config, "osutrack_enabled", True):
        with patch.object(history_data, "safe_async_get", new=AsyncMock(return_value=response)):
            result = await history_data.get_osutrack_history(123, 0, 30)

    assert result == [(1010.0, "2026-07-01", 9900), (1020.0, "2026-07-02", 9800)]


@pytest.mark.asyncio
async def test_local_history_wins_on_duplicate_date():
    from nonebot_plugin_osubot import history_data

    external = [(1000.0, "2026-07-01", 10000), (1010.0, "2026-07-02", 9900)]
    with patch.object(history_data, "get_osutrack_history", new=AsyncMock(return_value=external)):
        result, used_external = await history_data.merge_osutrack_history(
            123,
            0,
            [(1005.0, "2026-07-01", 9950)],
            30,
        )

    assert result == [(1005.0, "2026-07-01", 9950), (1010.0, "2026-07-02", 9900)]
    assert used_external is True
