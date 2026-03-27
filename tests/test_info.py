"""Tests for /info command matcher."""

import base64
import pytest
from unittest.mock import AsyncMock, patch
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"
INFO_MODULE = "nonebot_plugin_osubot.matcher.info"

FAKE_IMG = b"FAKE_IMAGE"
FAKE_IMG_B64 = base64.b64encode(FAKE_IMG).decode()


def _img_msg(event):
    return Message(
        [
            MessageSegment.reply(event.message_id),
            MessageSegment.image(file=f"base64://{FAKE_IMG_B64}"),
        ]
    )


def _text_msg(event, text):
    return Message(
        [
            MessageSegment.reply(event.message_id),
            MessageSegment.text(text),
        ]
    )


@pytest.mark.asyncio
async def test_info_not_bound(app: App):
    """/info ：用户未绑定，split_msg 注入 error，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.info import info
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/info"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(info) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                _text_msg(event, "该账号尚未绑定，请输入 /bind 用户名 绑定账号"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_info_success(app: App):
    """/info ：成功查询，调用 draw_info 并回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.info import info
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/info"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{INFO_MODULE}.draw_info", new=AsyncMock(return_value=FAKE_IMG)):
            async with app.test_matcher(info) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()


@pytest.mark.asyncio
async def test_info_network_error(app: App):
    """/info ：draw_info 抛出 NetworkError，回复错误消息。"""
    try:
        from nonebot_plugin_osubot.matcher.info import info
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_name="test_player", lazer_mode=False)

    event = fake_group_message_event_v11(message=Message("/info"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{INFO_MODULE}.draw_info", new=AsyncMock(side_effect=NetworkError("连接超时"))):
            async with app.test_matcher(info) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    _text_msg(event, "在查找用户：test_player osu模式 0日内 成绩时连接超时"),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_info_with_day(app: App):
    """/info #7 ：指定对比天数，draw_info 被调用时 day=7。"""
    try:
        from nonebot_plugin_osubot.matcher.info import info
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/info #7"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{INFO_MODULE}.draw_info", new=AsyncMock(return_value=FAKE_IMG)) as mock_draw:
            async with app.test_matcher(info) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()

    mock_draw.assert_awaited_once()
    assert mock_draw.call_args.args[2] == 7  # day 参数
