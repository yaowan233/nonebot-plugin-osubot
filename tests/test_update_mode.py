"""Tests for /更新模式 and /切换lazer commands."""

import pytest
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

MODULE = "nonebot_plugin_osubot.matcher.update_mode"


# ---------------------------------------------------------------------------
# /更新模式
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_mode_not_bound(app: App):
    """'/更新模式 1' when not bound should reply with a bind reminder."""
    try:
        from nonebot_plugin_osubot.matcher.update_mode import update_mode
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None  # not bound

    event = fake_group_message_event_v11(message=Message("/更新模式 1"))

    with patch_session(MODULE, session):
        async with app.test_matcher(update_mode) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message(
                    [
                        MessageSegment.reply(1),
                        MessageSegment.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号"),
                    ]
                ),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_update_mode_no_input(app: App):
    """'/更新模式' with no number when bound should reply with a prompt."""
    try:
        from nonebot_plugin_osubot.matcher.update_mode import update_mode
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/更新模式"))

    with patch_session(MODULE, session):
        async with app.test_matcher(update_mode) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([MessageSegment.reply(1), MessageSegment.text("请输入需要更新内容的模式")]),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode_input, expected_name",
    [
        ("0", "osu"),
        ("1", "taiko"),
        ("2", "fruits"),
        ("3", "mania"),
    ],
)
async def test_update_mode_valid(app: App, mode_input: str, expected_name: str):
    """'/更新模式 N' with a valid mode number should update the DB and reply."""
    try:
        from nonebot_plugin_osubot.matcher.update_mode import update_mode
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message(f"/更新模式 {mode_input}"))

    with patch_session(MODULE, session):
        async with app.test_matcher(update_mode) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message(
                    [
                        MessageSegment.reply(1),
                        MessageSegment.text(f"已将默认模式更改为 {expected_name}"),
                    ]
                ),
                result={"message_id": 1},
            )
            ctx.should_finished()

    session.execute.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_mode_invalid(app: App):
    """'/更新模式 5' with an out-of-range number should reply with an error."""
    try:
        from nonebot_plugin_osubot.matcher.update_mode import update_mode
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/更新模式 5"))

    with patch_session(MODULE, session):
        async with app.test_matcher(update_mode) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([MessageSegment.reply(1), MessageSegment.text("请输入正确的模式 0-3")]),
                result={"message_id": 1},
            )
            ctx.should_finished()


# ---------------------------------------------------------------------------
# /切换lazer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_toggle_lazer_not_bound(app: App):
    """'/切换lazer' when not bound should reply with a bind reminder."""
    try:
        from nonebot_plugin_osubot.matcher.update_mode import update_lazer
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None  # not bound

    event = fake_group_message_event_v11(message=Message("/切换lazer"))

    with patch_session(MODULE, session):
        async with app.test_matcher(update_lazer) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message(
                    [
                        MessageSegment.reply(1),
                        MessageSegment.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号"),
                    ]
                ),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_toggle_lazer_enable(app: App):
    """'/切换lazer' when lazer_mode=False should enable lazer and reply."""
    try:
        from nonebot_plugin_osubot.matcher.update_mode import update_lazer
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(lazer_mode=False)

    event = fake_group_message_event_v11(message=Message("/切换lazer"))

    with patch_session(MODULE, session):
        async with app.test_matcher(update_lazer) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([MessageSegment.reply(1), MessageSegment.text("已开启lazer模式")]),
                result={"message_id": 1},
            )
            ctx.should_finished()

    session.execute.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_lazer_disable(app: App):
    """'/切换lazer' when lazer_mode=True should disable lazer and reply."""
    try:
        from nonebot_plugin_osubot.matcher.update_mode import update_lazer
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(lazer_mode=True)

    event = fake_group_message_event_v11(message=Message("/切换lazer"))

    with patch_session(MODULE, session):
        async with app.test_matcher(update_lazer) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([MessageSegment.reply(1), MessageSegment.text("已关闭lazer模式")]),
                result={"message_id": 1},
            )
            ctx.should_finished()

    session.execute.assert_called_once()
    session.commit.assert_called_once()
