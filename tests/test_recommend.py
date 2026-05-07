"""Tests for recommend matcher (mayumi.xyz API)"""

import base64
import pytest
from unittest.mock import AsyncMock, patch
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"
RECOMMEND_MODULE = "nonebot_plugin_osubot.matcher.recommend"

FAKE_RECOMMEND_IMG = b"FAKE_RECOMMEND_IMAGE"


def text_msg(event, text: str) -> Message:
    return Message([MessageSegment.reply(event.message_id), MessageSegment.text(text)])


def img_msg(event, raw: bytes) -> Message:
    return Message(
        [
            MessageSegment.reply(event.message_id),
            MessageSegment.image(file=f"base64://{base64.b64encode(raw).decode()}"),
        ]
    )


def make_recommend_data(player_id=3162675, mode="taiko", count=3):
    """构造 RecommendData mock 对象"""
    from nonebot_plugin_osubot.schema.alphaosu import RecommendData, RecommendItem

    items = [
        RecommendItem(
            map_id=4571494 + i,
            mod=0,
            mod_str="NM",
            stars=4.0 + i * 0.1,
            pred_pp=160.0 + i * 5,
            pred_acc=98.0 + i * 0.1,
            final_score=155.0 + i * 3,
            title=f"Test Song {i} [Oni]",
            beatmapset_id=1927114 + i,
        )
        for i in range(count)
    ]
    return RecommendData(player_id=player_id, mode=mode, recommendations=items)


# ============================================================
# 未绑定账号
# ============================================================


@pytest.mark.asyncio
async def test_recommend_not_bound(app: App):
    """/推荐 未绑定账号 → 回复绑定提示"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/推荐"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(recommend) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "该账号尚未绑定，请输入 /bind 用户名 绑定账号"),
                result={"message_id": 1},
            )
            ctx.should_finished()


# ============================================================
# API 返回空推荐列表
# ============================================================


@pytest.mark.asyncio
async def test_recommend_empty_list(app: App):
    """/推荐 API 返回空列表 → 回复pp过低"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
        from nonebot_plugin_osubot.schema.alphaosu import RecommendData
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=3162675, osu_mode=1)

    empty_data = RecommendData(player_id=3162675, mode="taiko", recommendations=[])

    event = fake_group_message_event_v11(message=Message("/推荐"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{RECOMMEND_MODULE}.get_recommend", new=AsyncMock(return_value=empty_data)):
            async with app.test_matcher(recommend) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "该玩家pp过低，暂无推荐\n可以试试多打打图提升pp后再来哦"),
                    result={"message_id": 1},
                )


@pytest.mark.asyncio
async def test_recommend_detail_response(app: App):
    """/推荐 API 返回 detail（不在模型中）→ 回复pp过低"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
        from nonebot_plugin_osubot.schema.alphaosu import RecommendData
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_mode=0)

    detail_data = RecommendData(detail="该玩家不在模型中，暂无推荐")

    event = fake_group_message_event_v11(message=Message("/recommend"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{RECOMMEND_MODULE}.get_recommend", new=AsyncMock(return_value=detail_data)):
            async with app.test_matcher(recommend) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "该玩家pp过低，暂无推荐\n可以试试多打打图提升pp后再来哦"),
                    result={"message_id": 1},
                )


# ============================================================
# 正常推荐（taiko 模式）
# ============================================================


@pytest.mark.asyncio
async def test_recommend_success_taiko(app: App):
    """/推荐 taiko模式 成功 → 发送推荐图片"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=3162675, osu_mode=1)

    recommend_data = make_recommend_data(mode="taiko", count=5)

    event = fake_group_message_event_v11(message=Message("/推荐"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{RECOMMEND_MODULE}.get_recommend", new=AsyncMock(return_value=recommend_data)):
            with patch(f"{RECOMMEND_MODULE}.draw_recommend", new=AsyncMock(return_value=FAKE_RECOMMEND_IMG)):
                async with app.test_matcher(recommend) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        img_msg(event, FAKE_RECOMMEND_IMG),
                        result={"message_id": 1},
                    )


# ============================================================
# 正常推荐（osu 模式）
# ============================================================


@pytest.mark.asyncio
async def test_recommend_success_osu(app: App):
    """/recommend osu模式 成功 → 发送推荐图片"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_mode=0)

    recommend_data = make_recommend_data(player_id=114514, mode="osu", count=10)

    event = fake_group_message_event_v11(message=Message("/recommend"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{RECOMMEND_MODULE}.get_recommend", new=AsyncMock(return_value=recommend_data)):
            with patch(f"{RECOMMEND_MODULE}.draw_recommend", new=AsyncMock(return_value=FAKE_RECOMMEND_IMG)):
                async with app.test_matcher(recommend) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        img_msg(event, FAKE_RECOMMEND_IMG),
                        result={"message_id": 1},
                    )


# ============================================================
# 网络错误
# ============================================================


@pytest.mark.asyncio
async def test_recommend_network_error(app: App):
    """/推荐 get_recommend 抛出网络异常 → 回复错误信息"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=3162675, osu_name="TestPlayer", osu_mode=1)

    event = fake_group_message_event_v11(message=Message("/推荐"))

    with patch_session(UTILS_MODULE, session):
        with patch(
            f"{RECOMMEND_MODULE}.get_recommend",
            new=AsyncMock(side_effect=NetworkError("连接超时")),
        ):
            async with app.test_matcher(recommend) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "在查找用户：TestPlayer taiko模式 stable模式下时 连接超时"),
                    result={"message_id": 1},
                )
