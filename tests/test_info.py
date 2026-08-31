"""Tests for /info command matcher."""

import base64
import pytest
from io import BytesIO
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


@pytest.mark.asyncio
async def test_g0v0_explicit_mode_overrides_bound_default(app: App):
    from nonebot_plugin_osubot.matcher.info import info

    import nonebot

    session = make_mock_session()
    session.scalar.side_effect = [None, make_mock_user(osu_id=408, osu_name="Chestnut", osu_mode=0)]
    event = fake_group_message_event_v11(message=Message("/info :4 &gu"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{INFO_MODULE}.draw_info", new=AsyncMock(return_value=FAKE_IMG)) as mock_draw:
            async with app.test_matcher(info) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()

    mock_draw.assert_awaited_once_with(408, "rxosu", 0, "g0v0")


@pytest.mark.asyncio
async def test_ppysb_uses_bound_default_mode(app: App):
    from nonebot_plugin_osubot.matcher.info import info

    import nonebot

    session = make_mock_session()
    session.scalar.side_effect = [None, make_mock_user(osu_id=42, osu_name="Akatsuki", osu_mode=5)]
    event = fake_group_message_event_v11(message=Message("/info &sb"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{INFO_MODULE}.draw_info", new=AsyncMock(return_value=FAKE_IMG)) as mock_draw:
            async with app.test_matcher(info) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()

    mock_draw.assert_awaited_once_with(42, "rxtaiko", 0, "ppysb")


@pytest.mark.asyncio
async def test_g0v0_info_does_not_read_official_snapshots(tmp_path):
    from nonebot_plugin_osubot.draw import info as draw_info_module
    from nonebot_plugin_osubot.schema.user import GradeCounts, Level, UnifiedUser, UserStatistics

    statistics = UserStatistics(
        grade_counts=GradeCounts(ssh=0, ss=1, sh=2, s=3, a=4),
        hit_accuracy=98.76,
        is_ranked=True,
        level=Level(current=100, progress=0),
        maximum_combo=500,
        play_count=100,
        play_time=3600,
        pp=1234.5,
        ranked_score=3_000_000,
        replays_watched_by_others=10,
        total_hits=20_000,
        total_score=4_000_000,
        global_rank=1000,
        country_rank=100,
    )
    user = UnifiedUser(
        avatar_url="https://lazer.g0v0.top/avatar/408",
        country_code="CN",
        id=408,
        username="Chestnut",
        is_supporter=False,
        statistics=statistics,
    )

    with (
        patch.object(draw_info_module, "user_cache_path", tmp_path),
        patch.object(draw_info_module, "get_user_scores", new=AsyncMock(return_value=[])),
        patch.object(draw_info_module, "get_user_info_data", new=AsyncMock(return_value=user)),
        patch.object(draw_info_module, "_player_avatar_data_uri", new=AsyncMock(return_value="avatar")),
        patch.object(draw_info_module, "_team_icon_data", new=AsyncMock(return_value=None)),
        patch.object(draw_info_module, "render_info_svg", new=AsyncMock(return_value=BytesIO(FAKE_IMG))),
        patch.object(
            draw_info_module,
            "get_session",
            side_effect=AssertionError("g0v0 info must not query official InfoData"),
        ),
    ):
        result = await draw_info_module.draw_info(408, "osu", 7, "g0v0")

    assert result == FAKE_IMG
