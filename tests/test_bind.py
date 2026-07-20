"""Tests for /bind, /unbind, /sbbind, /sbunbind commands."""

import pytest
from unittest.mock import AsyncMock, patch
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

MODULE = "nonebot_plugin_osubot.matcher.bind"
INFO_BIND_MODULE = "nonebot_plugin_osubot.info.bind"


# ---------------------------------------------------------------------------
# /bind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bind_no_name(app: App):
    """'/bind' with no username should reply with a prompt and finish."""
    try:
        from nonebot_plugin_osubot.matcher.bind import bind
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    event = fake_group_message_event_v11(message=Message("/bind "))

    async with app.test_matcher(bind) as ctx:
        adapter = nonebot.get_adapter(OnebotV11Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter)
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            Message(
                [MessageSegment.reply(1), MessageSegment.text("请在指令后输入 osu! 用户名、UID 或个人主页链接")]
            ),
            result={"message_id": 1},
        )
        ctx.should_finished()


@pytest.mark.asyncio
async def test_bind_already_bound(app: App):
    """'/bind username' when the QQ is already bound should reply with a hint."""
    try:
        from nonebot_plugin_osubot.matcher.bind import bind
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    mock_user = make_mock_user(osu_name="existing_player")
    session = make_mock_session()
    session.scalar.return_value = mock_user

    event = fake_group_message_event_v11(message=Message("/bind someone"))

    with patch_session(MODULE, session):
        async with app.test_matcher(bind) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message(
                    [
                        MessageSegment.reply(1),
                        MessageSegment.text("您已绑定existing_player，如需要解绑请输入/unbind"),
                    ]
                ),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_bind_success(app: App):
    """'/bind testuser' for an unbound account should call bind_user_info and send the result."""
    try:
        from nonebot_plugin_osubot.matcher.bind import bind
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None  # not yet bound

    success_msg = "成功绑定 testuser\n默认模式为 osu，可使用 /mode o、t、c、m 切换"
    event = fake_group_message_event_v11(message=Message("/bind testuser"))

    with patch_session(MODULE, session):
        with patch(f"{MODULE}.bind_user_info", new=AsyncMock(return_value=success_msg)):
            async with app.test_matcher(bind) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    Message([MessageSegment.reply(1), MessageSegment.text(success_msg)]),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_bind_user_not_found(app: App):
    """'/bind nobody' when the API can't find the user should reply with a failure message."""
    try:
        from nonebot_plugin_osubot.matcher.bind import bind
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/bind nobody"))

    with patch_session(MODULE, session):
        with patch(f"{MODULE}.bind_user_info", new=AsyncMock(side_effect=NetworkError("not found"))):
            async with app.test_matcher(bind) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    Message(
                        [
                            MessageSegment.reply(1),
                            MessageSegment.text("绑定失败，找不到叫 nobody 的人哦"),
                        ]
                    ),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_bind_numeric_username_uses_username_lookup():
    """bind_user_info uses the unified username/UID resolver."""
    from nonebot_plugin_osubot.info.bind import bind_user_info

    session = make_mock_session()
    mock_info = {"id": 114514, "username": "123456", "playmode": "osu"}

    with patch_session(INFO_BIND_MODULE, session):
        with patch(f"{INFO_BIND_MODULE}.get_osu_user", new=AsyncMock(return_value=mock_info)) as get_user:
            with patch(f"{INFO_BIND_MODULE}.update_users_info", new=AsyncMock()) as mock_update:
                msg = await bind_user_info("bind", "123456", "qq-user")

    get_user.assert_awaited_once_with("123456")
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    mock_update.assert_awaited_once_with([114514])
    assert msg == "成功绑定 123456\n默认模式为 osu，可使用 /mode o、t、c、m 切换"


@pytest.mark.asyncio
async def test_numeric_username_is_preferred_over_uid():
    from nonebot_plugin_osubot.api import get_osu_user

    numeric_user = {"id": 114514, "username": "123456"}
    with patch("nonebot_plugin_osubot.api.get_user_info", new=AsyncMock(return_value=numeric_user)) as request:
        assert await get_osu_user("123456") == numeric_user

    request.assert_awaited_once_with("https://osu.ppy.sh/api/v2/users/123456?key=username")


@pytest.mark.asyncio
async def test_explicit_uid_and_profile_url_use_id_lookup():
    from nonebot_plugin_osubot.api import get_osu_user

    user = {"id": 2, "username": "peppy"}
    with patch("nonebot_plugin_osubot.api.get_user_info", new=AsyncMock(return_value=user)) as request:
        assert await get_osu_user("id:2") == user
        assert await get_osu_user("https://osu.ppy.sh/users/2") == user

    assert request.await_args_list[0].args[0] == "https://osu.ppy.sh/api/v2/users/2?key=id"
    assert request.await_args_list[1].args[0] == "https://osu.ppy.sh/api/v2/users/2?key=id"


# ---------------------------------------------------------------------------
# /unbind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unbind_not_bound(app: App):
    """'/unbind' when not bound should reply '尚未绑定，无需解绑'."""
    try:
        from nonebot_plugin_osubot.matcher.bind import unbind
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None  # not bound

    event = fake_group_message_event_v11(message=Message("/unbind"))

    with patch_session(MODULE, session):
        async with app.test_matcher(unbind) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([MessageSegment.reply(1), MessageSegment.text("尚未绑定，无需解绑")]),
                result={"message_id": 1},
            )
            # .send() not .finish() — handler returns normally


@pytest.mark.asyncio
async def test_unbind_success(app: App):
    """'/unbind' when bound should delete the record and reply '解绑成功！'."""
    try:
        from nonebot_plugin_osubot.matcher.bind import unbind
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    mock_user = make_mock_user()
    session = make_mock_session()
    session.scalar.return_value = mock_user

    event = fake_group_message_event_v11(message=Message("/unbind"))

    with patch_session(MODULE, session):
        async with app.test_matcher(unbind) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([MessageSegment.reply(1), MessageSegment.text("解绑成功！")]),
                result={"message_id": 1},
            )
            # .send() not .finish() — handler returns normally

    # Verify the delete + commit actually happened
    session.execute.assert_called_once()
    session.commit.assert_called_once()
