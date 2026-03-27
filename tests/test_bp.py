"""Tests for /bp, /pfm (bplist), /tbp (todaybp) commands."""
import base64
import pytest
from io import BytesIO
from unittest.mock import AsyncMock, patch
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"
BP_MODULE = "nonebot_plugin_osubot.matcher.bp"

# 所有绘图函数返回这段固定字节，方便预测消息内容
FAKE_IMG = b"FAKE_IMAGE"
FAKE_IMG_B64 = base64.b64encode(FAKE_IMG).decode()


def _img_msg(event):
    """构造带 reply 的图片消息（alconna 对 OB11 导出格式）。"""
    return Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.image(file=f"base64://{FAKE_IMG_B64}"),
    ])


def _text_msg(event, text):
    return Message([
        MessageSegment.reply(event.message_id),
        MessageSegment.text(text),
    ])


# ---------------------------------------------------------------------------
# /bp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bp_not_bound(app: App):
    """/bp 1 ：用户未绑定，split_msg 会把 error 注入 state，发送提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None  # 未绑定

    event = fake_group_message_event_v11(message=Message("/bp 1"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(bp) as ctx:
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
async def test_bp_success(app: App):
    """/bp 1 ：成功查询，调用 draw_score 并回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/bp 1"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_score", new=AsyncMock(return_value=BytesIO(FAKE_IMG))):
            async with app.test_matcher(bp) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()


@pytest.mark.asyncio
async def test_bp_out_of_range(app: App):
    """/bp 201 ：超出范围，回复错误提示。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/bp 201"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(bp) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                _text_msg(event, "只允许查询bp 1-200 的成绩"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_bp_zero(app: App):
    """/bp 0 ：为 0，同样超出范围。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/bp 0"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(bp) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                _text_msg(event, "只允许查询bp 1-200 的成绩"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_bp_network_error(app: App):
    """/bp 1 ：draw_score 抛出 NetworkError，回复错误消息。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_name="test_player")

    event = fake_group_message_event_v11(message=Message("/bp 1"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_score", new=AsyncMock(side_effect=NetworkError("连接超时"))):
            async with app.test_matcher(bp) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    _text_msg(
                        event,
                        "在查找用户：test_player osu模式 bp1 stable模式下时 连接超时",
                    ),
                    result={"message_id": 1},
                )
                ctx.should_finished()


# ---------------------------------------------------------------------------
# /pfm (bplist)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pfm_success(app: App):
    """/pfm ：无范围参数，默认 1-200，调用 draw_bp 回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import pfm
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/pfm"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_bp", new=AsyncMock(return_value=BytesIO(FAKE_IMG))):
            async with app.test_matcher(pfm) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()


@pytest.mark.asyncio
async def test_pfm_invalid_range(app: App):
    """/pfm #200-100 ：low > high，回复范围错误。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import pfm
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    # split_msg 会解析 200-100 → state["range"] = "200-100"（low > high，不合法）
    event = fake_group_message_event_v11(message=Message("/pfm 200-100"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(pfm) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                _text_msg(event, "仅支持查询bp1-200"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_pfm_network_error(app: App):
    """/pfm ：draw_bp 抛出 NetworkError，回复错误消息。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import pfm
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_name="test_player")

    event = fake_group_message_event_v11(message=Message("/pfm"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_bp", new=AsyncMock(side_effect=NetworkError("超时"))):
            async with app.test_matcher(pfm) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    _text_msg(
                        event,
                        "在查找用户：test_player osu模式 bp1-200 stable模式下时 超时",
                    ),
                    result={"message_id": 1},
                )
                ctx.should_finished()


# ---------------------------------------------------------------------------
# /tbp (todaybp)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tbp_success(app: App):
    """/tbp ：调用 draw_bp project=tbp，回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.bp import tbp
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/tbp"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_bp", new=AsyncMock(return_value=BytesIO(FAKE_IMG))) as mock_draw:
            async with app.test_matcher(tbp) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()

    # 验证 project 参数是 "tbp"
    mock_draw.assert_awaited_once()
    assert mock_draw.call_args[0][0] == "tbp"
