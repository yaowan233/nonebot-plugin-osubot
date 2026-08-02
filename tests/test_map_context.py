from unittest.mock import AsyncMock, patch

import pytest
from nonebot.adapters.onebot.v11 import Message

from fake import fake_group_message_event_v11, fake_private_message_event_v11

CONTEXT_MODULE = "nonebot_plugin_osubot.matcher.map_context"


def test_group_context_is_shared_by_all_members_and_uses_latest_map():
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, remember_map

    first = fake_group_message_event_v11(user_id=10001)
    second = fake_group_message_event_v11(user_id=10002)

    remember_map(first, 12345)

    assert get_last_map_id(first) == "12345"
    assert get_last_map_id(second) == "12345"

    remember_map(second, 54321)

    assert get_last_map_id(first) == "54321"
    assert get_last_map_id(second) == "54321"


def test_different_groups_have_independent_contexts():
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, remember_map

    first = fake_group_message_event_v11(group_id=10001)
    second = fake_group_message_event_v11(group_id=10002)
    remember_map(first, 12345)

    assert get_last_map_id(first) == "12345"
    assert get_last_map_id(second) is None


def test_private_contexts_remain_scoped_by_user():
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, remember_map

    first = fake_private_message_event_v11(user_id=10001, original_message=Message("test"))
    second = fake_private_message_event_v11(user_id=10002, original_message=Message("test"))
    remember_map(first, 12345)

    assert get_last_map_id(first) == "12345"
    assert get_last_map_id(second) is None


@pytest.mark.asyncio
async def test_shared_context_resolves_and_caches_set_id():
    from nonebot_plugin_osubot.matcher.map_context import get_last_set_id, remember_map

    first = fake_group_message_event_v11(user_id=10001)
    second = fake_group_message_event_v11(user_id=10002)
    remember_map(first, 12345)

    with patch(f"{CONTEXT_MODULE}.osu_api", new=AsyncMock(return_value={"beatmapset_id": 67890})) as api:
        assert await get_last_set_id(second) == "67890"
        assert await get_last_set_id(second) == "67890"

    api.assert_awaited_once_with("map", map_id=12345)


@pytest.mark.asyncio
async def test_set_id_is_resolved_from_last_map():
    from nonebot_plugin_osubot.matcher.map_context import get_last_set_id, remember_map

    event = fake_group_message_event_v11()
    remember_map(event, 12345)

    with patch(f"{CONTEXT_MODULE}.osu_api", new=AsyncMock(return_value={"beatmapset_id": 67890})) as api:
        assert await get_last_set_id(event) == "67890"
        assert await get_last_set_id(event) == "67890"

    api.assert_awaited_once_with("map", map_id=12345)


@pytest.mark.asyncio
async def test_refreshing_same_map_preserves_known_set():
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, get_last_set_id, remember_map, remember_set

    event = fake_group_message_event_v11()
    remember_map(event, 12345, 67890)

    remember_map(event, 12345)
    remember_set(event, 67890)

    assert get_last_map_id(event) == "12345"
    assert await get_last_set_id(event) == "67890"


def test_recording_different_map_or_set_discards_stale_relation():
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, remember_map, remember_set

    event = fake_group_message_event_v11()
    remember_map(event, 12345, 67890)

    remember_map(event, 54321)
    remember_set(event, 9876)

    assert get_last_map_id(event) is None
