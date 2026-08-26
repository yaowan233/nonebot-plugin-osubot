from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App
from httpx import Response
from PIL import Image

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

MODULE = "nonebot_plugin_osubot.matcher.friend"
FAKE_IMG = b"friend-list-image"


def _friend(
    *,
    uid: int,
    online: bool = False,
    mutual: bool = False,
    last_visit: str | None = None,
    pp: float = 0,
    country: str = "",
):
    target = SimpleNamespace(
        username=f"user-{uid}",
        avatar_url=f"https://a.ppy.sh/{uid}",
        is_online=online,
        is_supporter=False,
        last_visit=last_visit,
        statistics=SimpleNamespace(pp=pp),
        country_code=country,
    )
    return SimpleNamespace(target_id=uid, mutual=mutual, target=target)


@pytest.mark.asyncio
async def test_friend_authorization_timeout_is_silent(app: App):
    from nonebot_plugin_osubot.friend_oauth import AuthorizationSession, OAuthAuthorizationTimeout
    from nonebot_plugin_osubot.matcher.friend import friend

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()
    authorization = AuthorizationSession(
        session_id="session-id",
        poll_token="poll-token",
        expires_in=60,
        redirect_uri="https://mayumi.xyz/api/osubot/oauth/callback",
        authorize_url="https://osu.ppy.sh/oauth/authorize?...",
    )
    event = fake_group_message_event_v11(message=Message("/friend"))
    prompt = (
        "首次查询需要授权读取 osu! 好友列表。请在 1 分钟内点击链接完成授权，"
        "完成后本次查询会自动继续：\nhttps://osu.ppy.sh/oauth/authorize?..."
    )

    with patch_session(MODULE, session):
        with patch(f"{MODULE}.get_valid_oauth", new=AsyncMock(return_value=None)):
            with patch(f"{MODULE}.begin_authorization", new=AsyncMock(return_value=authorization)):
                with patch(
                    f"{MODULE}.wait_for_authorization",
                    new=AsyncMock(side_effect=OAuthAuthorizationTimeout("授权链接已过期，请重新发送 /friend")),
                ):
                    with patch(f"{MODULE}._recall_oauth_message", new=AsyncMock()) as recall:
                        with patch(f"{MODULE}.discard_authorization", new=AsyncMock()) as discard:
                            async with app.test_matcher(friend) as ctx:
                                adapter = nonebot.get_adapter(OnebotV11Adapter)
                                bot = ctx.create_bot(base=Bot, adapter=adapter)
                                ctx.receive_event(bot, event)
                                ctx.should_call_send(
                                    event,
                                    Message([MessageSegment.reply(1), MessageSegment.text(prompt)]),
                                    result={"message_id": 1},
                                )

    recall.assert_awaited_once()
    discard.assert_awaited_once_with(authorization)


@pytest.mark.asyncio
async def test_pending_authorization_raises_timeout(after_nonebot_init: None):
    from nonebot_plugin_osubot.friend_oauth import (
        AuthorizationSession,
        OAuthAuthorizationTimeout,
        wait_for_authorization,
    )

    authorization = AuthorizationSession(
        session_id="session-id",
        poll_token="poll-token",
        expires_in=1,
        redirect_uri="https://mayumi.xyz/api/osubot/oauth/callback",
        authorize_url="https://osu.ppy.sh/oauth/authorize?...",
    )

    with patch("nonebot_plugin_osubot.friend_oauth.monotonic", side_effect=[0, 0, 0, 2]):
        with patch(
            "nonebot_plugin_osubot.friend_oauth.safe_async_get",
            new=AsyncMock(return_value=Response(202, json={"status": "pending"})),
        ):
            with patch("nonebot_plugin_osubot.friend_oauth.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(OAuthAuthorizationTimeout):
                    await wait_for_authorization(authorization)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "expected_start", "expected_end"),
    [("/friend", 1, 50), ("/friend 11-75", 11, 60)],
)
async def test_friend_list_render_is_limited(
    app: App,
    command: str,
    expected_start: int,
    expected_end: int,
):
    from nonebot_plugin_osubot.matcher.friend import friend

    import base64
    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()
    oauth = SimpleNamespace(access_token="access", osu_name="test-player", osu_id=42)
    friends = [_friend(uid=index) for index in range(1, 76)]
    event = fake_group_message_event_v11(message=Message(command))
    draw = AsyncMock(return_value=FAKE_IMG)

    with patch_session(MODULE, session):
        with patch(f"{MODULE}.get_valid_oauth", new=AsyncMock(return_value=oauth)):
            with patch(f"{MODULE}.get_user_friends", new=AsyncMock(return_value=friends)):
                with patch(f"{MODULE}.draw_friend_list", new=draw):
                    async with app.test_matcher(friend) as ctx:
                        adapter = nonebot.get_adapter(OnebotV11Adapter)
                        bot = ctx.create_bot(base=Bot, adapter=adapter)
                        ctx.receive_event(bot, event)
                        ctx.should_call_send(
                            event,
                            Message(
                                [
                                    MessageSegment.reply(1),
                                    MessageSegment.image(file=f"base64://{base64.b64encode(FAKE_IMG).decode()}"),
                                ]
                            ),
                            result={"message_id": 1},
                        )
                        ctx.should_finished()

    payload = draw.await_args.args[0]
    assert payload["total"] == 75
    assert payload["start"] == expected_start
    assert payload["end"] == expected_end
    assert len(payload["friends"]) == 50


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


def test_combined_friend_filters(after_nonebot_init: None):
    from nonebot_plugin_osubot.matcher.friend import _filter_friends, _parse_conditions

    conditions, remaining = _parse_conditions("pp>=300 mutual=true country=JP")
    friends = [
        _friend(uid=1, pp=400, mutual=True, country="JP"),
        _friend(uid=2, pp=250, mutual=True, country="JP"),
        _friend(uid=3, pp=500, mutual=False, country="JP"),
        _friend(uid=4, pp=600, mutual=True, country="CN"),
    ]

    assert remaining == ""
    assert [item.target_id for item in _filter_friends(friends, conditions)] == [1]


@pytest.mark.asyncio
async def test_friend_avatar_uses_dedicated_cache_name(after_nonebot_init: None, tmp_path):
    from nonebot_plugin_osubot.draw.friend import _load_avatar_data_uri

    image = Image.new("RGBA", (128, 128), "red")
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    with patch("nonebot_plugin_osubot.draw.friend.user_cache_path", tmp_path):
        with patch(
            "nonebot_plugin_osubot.draw.friend.safe_async_get",
            new=AsyncMock(return_value=Response(200, content=buffer.getvalue())),
        ):
            result = await _load_avatar_data_uri(42, "https://a.ppy.sh/42")

    cache_dir = tmp_path / "42"
    assert result.startswith("data:image/png;base64,")
    assert (cache_dir / "friend-avatar-64.png").is_file()
    assert list(cache_dir.glob("icon*.*")) == []


@pytest.mark.asyncio
async def test_oauth_url_message_is_recalled(after_nonebot_init: None):
    from nonebot_plugin_osubot.matcher.friend import _recall_oauth_message

    receipt = SimpleNamespace(recall=AsyncMock())

    await _recall_oauth_message(receipt)

    receipt.recall.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_oauth_url_recall_failure_does_not_break_authorization(after_nonebot_init: None):
    from nonebot_plugin_osubot.matcher.friend import _recall_oauth_message

    receipt = SimpleNamespace(recall=AsyncMock(side_effect=RuntimeError("recall unsupported")))

    await _recall_oauth_message(receipt)


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
