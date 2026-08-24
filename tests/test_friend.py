from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response

from utils import make_mock_session, make_mock_user, patch_session


def _friend(*, uid: int, online: bool = False, mutual: bool = False, last_visit: str | None = None):
    target = SimpleNamespace(
        username=f"user-{uid}",
        is_online=online,
        last_visit=last_visit,
    )
    return SimpleNamespace(target_id=uid, mutual=mutual, target=target)


def test_sort_suffixes_apply_to_every_field(after_nonebot_init: None):
    from nonebot_plugin_osubot.matcher.friend import FriendSort, _parse_sort

    assert _parse_sort(":pp- 1-10") == (FriendSort("pp", "desc"), "1-10")
    assert _parse_sort(":acc2") == (FriendSort("acc", "asc"), "")
    assert _parse_sort(":t+") == (FriendSort("time", "asc"), "")
    assert _parse_sort(":u2") == (FriendSort("uid", "asc"), "")
    assert _parse_sort(":c2") == (FriendSort("country", "asc"), "")
    assert _parse_sort(":n2") == (FriendSort("name", "asc"), "")


def test_boolean_sort_keeps_all_friends(after_nonebot_init: None):
    from nonebot_plugin_osubot.matcher.friend import FriendSort, _sort_friends

    friends = [
        _friend(uid=1, online=True, mutual=False),
        _friend(uid=2, online=False, mutual=True),
        _friend(uid=3, online=True, mutual=True),
    ]

    assert [item.target_id for item in _sort_friends(friends, FriendSort("online", "desc"))] == [1, 3, 2]
    assert [item.target_id for item in _sort_friends(friends, FriendSort("online", "asc"))] == [2, 1, 3]
    assert [item.target_id for item in _sort_friends(friends, FriendSort("mutual", "desc"))] == [2, 3, 1]


def test_last_visit_sort_accepts_missing_and_timezone_values(after_nonebot_init: None):
    from nonebot_plugin_osubot.matcher.friend import FriendSort, _sort_friends

    friends = [
        _friend(uid=1, last_visit="2026-08-24T10:00:00Z"),
        _friend(uid=2),
        _friend(uid=3, last_visit="2026-08-24T11:00:00"),
    ]

    assert [item.target_id for item in _sort_friends(friends, FriendSort("time", "asc"))] == [2, 1, 3]


@pytest.mark.asyncio
async def test_relay_authorization_round_trip(after_nonebot_init: None):
    from nonebot_plugin_osubot.friend_oauth import begin_authorization, wait_for_authorization

    created = Response(
        201,
        json={
            "session_id": "session-id",
            "poll_token": "poll-token",
            "expires_in": 60,
            "redirect_uri": "https://mayumi.xyz/api/osubot/oauth/callback",
        },
    )
    pending = Response(202, json={"status": "pending"})
    complete = Response(200, json={"status": "complete", "code": "oauth-code"})

    with patch(
        "nonebot_plugin_osubot.friend_oauth.safe_async_post",
        new=AsyncMock(return_value=created),
    ):
        with patch("nonebot_plugin_osubot.friend_oauth.get_oauth_client_id", return_value=1):
            with patch("nonebot_plugin_osubot.friend_oauth.get_oauth_client_secret", return_value="secret"):
                with patch(
                    "nonebot_plugin_osubot.friend_oauth.build_oauth_authorize_url",
                    return_value="https://osu.ppy.sh/oauth/authorize?...",
                ):
                    authorization = await begin_authorization()

    with patch(
        "nonebot_plugin_osubot.friend_oauth.safe_async_get",
        new=AsyncMock(side_effect=[pending, complete]),
    ):
        with patch("nonebot_plugin_osubot.friend_oauth.asyncio.sleep", new=AsyncMock()):
            assert await wait_for_authorization(authorization) == "oauth-code"


@pytest.mark.asyncio
async def test_oauth_account_must_match_bound_user(after_nonebot_init: None):
    from nonebot_plugin_osubot.friend_oauth import OAuthAccountMismatch, complete_authorization

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=123, osu_name="bound-user")
    token = {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}

    with patch_session("nonebot_plugin_osubot.friend_oauth", session):
        with patch(
            "nonebot_plugin_osubot.friend_oauth.exchange_oauth_code",
            new=AsyncMock(return_value=token),
        ):
            with patch(
                "nonebot_plugin_osubot.friend_oauth.get_me_with_token",
                new=AsyncMock(return_value={"id": 456, "username": "other-user"}),
            ):
                with pytest.raises(OAuthAccountMismatch, match="bound-user"):
                    await complete_authorization("platform-user", "code", "https://example.com/callback")

    session.add.assert_not_called()
    session.commit.assert_not_awaited()
