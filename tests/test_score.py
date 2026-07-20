"""Tests for /score command matcher."""

import base64
import pytest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"
SCORE_MODULE = "nonebot_plugin_osubot.matcher.score"

FAKE_IMG = b"FAKE_IMAGE"
FAKE_IMG_B64 = base64.b64encode(FAKE_IMG).decode()


@pytest.mark.asyncio
async def test_draw_score_can_return_selected_beatmap_context(tmp_path):
    """The drawing layer exposes the exact score selected after filtering/indexing."""
    from nonebot_plugin_osubot.draw.score import draw_score

    score = SimpleNamespace(beatmap=SimpleNamespace(id=24680, set_id=13579))
    user = SimpleNamespace(id=114514)
    module = "nonebot_plugin_osubot.draw.score"

    with (
        patch(f"{module}.map_path", tmp_path),
        patch(f"{module}.get_user_scores", new=AsyncMock(return_value=[score])),
        patch(f"{module}.get_user_info_data", new=AsyncMock(return_value=user)),
        patch(f"{module}.osu_api", new=AsyncMock(return_value={})),
        patch(f"{module}.download_osu", new=AsyncMock()),
        patch(f"{module}.cal_score_info", side_effect=lambda _, value, __: value),
        patch(f"{module}.draw_score_pic", new=AsyncMock(return_value=BytesIO(FAKE_IMG))),
    ):
        image, map_id, set_id = await draw_score("recent", 114514, False, "osu", [], [], return_context=True)

    assert image.getvalue() == FAKE_IMG
    assert map_id == 24680
    assert set_id == 13579


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
async def test_score_not_bound(app: App):
    """/score 114514 ：用户未绑定，split_msg 注入 error，发送提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.score import score
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None  # 未绑定

    event = fake_group_message_event_v11(message=Message("/score 114514"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(score) as ctx:
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
async def test_score_no_target(app: App):
    """/score：没有参数或最近谱面时提示用户。"""
    try:
        from nonebot_plugin_osubot.matcher.score import score
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/score"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(score) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                _text_msg(event, "请输入谱面ID，或先查询一张谱面"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_score_success(app: App):
    """/score 114514 ：成功查询，调用 get_score_data 并回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.score import score
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()

    event = fake_group_message_event_v11(message=Message("/score 114514"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{SCORE_MODULE}.get_score_data", new=AsyncMock(return_value=BytesIO(FAKE_IMG))):
            async with app.test_matcher(score) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()


@pytest.mark.asyncio
async def test_score_uses_last_map_when_target_is_omitted(app: App):
    from nonebot_plugin_osubot.matcher.score import score
    from nonebot_plugin_osubot.matcher.map_context import remember_map

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user()
    event = fake_group_message_event_v11(message=Message("/sc"))
    remember_map(event, 114514)

    with patch_session(UTILS_MODULE, session):
        with patch(f"{SCORE_MODULE}.get_score_data", new=AsyncMock(return_value=BytesIO(FAKE_IMG))) as get_score:
            async with app.test_matcher(score) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, _img_msg(event), result={"message_id": 1})
                ctx.should_finished()

    assert get_score.call_args.args[4] == "114514"


@pytest.mark.asyncio
async def test_score_network_error(app: App):
    """/score 114514 ：get_score_data 抛出 NetworkError，回复错误消息。"""
    try:
        from nonebot_plugin_osubot.matcher.score import score
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")

    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_name="test_player", lazer_mode=False)

    event = fake_group_message_event_v11(message=Message("/score 114514"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{SCORE_MODULE}.get_score_data", new=AsyncMock(side_effect=NetworkError("连接超时"))):
            async with app.test_matcher(score) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    _text_msg(event, "在查找用户：test_player osu模式 stable模式下 成绩时 连接超时"),
                    result={"message_id": 1},
                )
                ctx.should_finished()
