"""Tests for /bind, /unbind, /sbbind, /sbunbind commands."""
import pytest
from unittest.mock import AsyncMock, patch
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

MODULE = "nonebot_plugin_osubot.matcher.bind"


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
            Message([MessageSegment.reply(1), MessageSegment.text("请在指令后输入您的 osuid")]),
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
                Message([
                    MessageSegment.reply(1),
                    MessageSegment.text("您已绑定existing_player，如需要解绑请输入/unbind"),
                ]),
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

    success_msg = "成功绑定 testuser\n默认模式为 osu，若更改模式至其他模式，如 mania，请输入 /更新模式 3"
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
                    Message([
                        MessageSegment.reply(1),
                        MessageSegment.text("绑定失败，找不到叫 nobody 的人哦"),
                    ]),
                    result={"message_id": 1},
                )
                ctx.should_finished()


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
