"""简单 matcher 测试：mu / osu_help / history / url_match / match / rating"""

import importlib

import pytest
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"


def text_msg(event, text: str) -> Message:
    return Message([MessageSegment.reply(event.message_id), MessageSegment.text(text)])


# ---------------------------------------------------------------------------
# /mu
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mu_not_bound(app: App):
    """/mu：未绑定时回复错误并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.mu import mu
    except ImportError:
        pytest.skip()
    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None  # 未绑定

    event = fake_group_message_event_v11(message=Message("/mu"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(mu) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "该账号尚未绑定，请输入 /bind 用户名 绑定账号"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_mu_success(app: App):
    """/mu：已绑定时回复用户主页链接。"""
    try:
        from nonebot_plugin_osubot.matcher.mu import mu
    except ImportError:
        pytest.skip()
    import nonebot

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/mu"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(mu) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "https://osu.ppy.sh/u/114514"),
                result={"message_id": 1},
            )
            ctx.should_finished()


# ---------------------------------------------------------------------------
# /osuhelp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_osu_help_default(app: App):
    """/osuhelp：无参数时发送帮助图片。"""
    try:
        from nonebot_plugin_osubot.matcher.osu_help import osu_help, img1
    except ImportError:
        pytest.skip()
    import nonebot

    event = fake_group_message_event_v11(message=Message("/osuhelp"))

    async with app.test_matcher(osu_help) as ctx:
        adapter = nonebot.get_adapter(OnebotV11Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter)
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            Message(
                [
                    MessageSegment.reply(1),
                    MessageSegment.image(file=f"base64://{__import__('base64').b64encode(img1).decode()}"),
                ]
            ),
            result={"message_id": 1},
        )
        ctx.should_finished()


def test_osu_help_default_image_is_complete_command_reference(after_nonebot_init: None):
    from nonebot_plugin_osubot.matcher.osu_help import img1, img2

    assert img1 == img2


@pytest.mark.asyncio
async def test_osu_help_detail(app: App):
    """/osuhelp detail：发送详情图片。"""
    try:
        from nonebot_plugin_osubot.matcher.osu_help import osu_help, img2
    except ImportError:
        pytest.skip()
    import nonebot

    event = fake_group_message_event_v11(message=Message("/osuhelp detail"))

    async with app.test_matcher(osu_help) as ctx:
        adapter = nonebot.get_adapter(OnebotV11Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter)
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            Message(
                [
                    MessageSegment.reply(1),
                    MessageSegment.image(file=f"base64://{__import__('base64').b64encode(img2).decode()}"),
                ]
            ),
            result={"message_id": 1},
        )
        ctx.should_finished()


@pytest.mark.asyncio
async def test_osu_help_detail_chinese(app: App):
    """/osuhelp 详细：中文参数同样发送详情图片。"""
    try:
        from nonebot_plugin_osubot.matcher.osu_help import osu_help, img2
    except ImportError:
        pytest.skip()
    import nonebot

    event = fake_group_message_event_v11(message=Message("/osuhelp 详细"))

    async with app.test_matcher(osu_help) as ctx:
        adapter = nonebot.get_adapter(OnebotV11Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter)
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            Message(
                [
                    MessageSegment.reply(1),
                    MessageSegment.image(file=f"base64://{__import__('base64').b64encode(img2).decode()}"),
                ]
            ),
            result={"message_id": 1},
        )
        ctx.should_finished()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "topic"),
    [
        ("/oh mode", "mode"),
        ("/oh /vp", "map"),
        ("/oh bpa", "score"),
    ],
)
async def test_osu_help_topic(app: App, command: str, topic: str):
    """/oh accepts both topic names and concrete commands."""
    from nonebot_plugin_osubot.matcher.osu_help import HELP_TOPICS, osu_help

    import nonebot

    event = fake_group_message_event_v11(message=Message(command))
    async with app.test_matcher(osu_help) as ctx:
        adapter = nonebot.get_adapter(OnebotV11Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter)
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, text_msg(event, HELP_TOPICS[topic]), result={"message_id": 1})
        ctx.should_finished()


# ---------------------------------------------------------------------------
# /history
# ---------------------------------------------------------------------------

HISTORY_MODULE = "nonebot_plugin_osubot.matcher.history"


@pytest.mark.asyncio
async def test_history_not_bound(app: App):
    """/history：未绑定时回复错误并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.history import history
    except ImportError:
        pytest.skip()
    import nonebot

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/history"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(history) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "该账号尚未绑定，请输入 /bind 用户名 绑定账号"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_history_no_data(app: App):
    """/history：DB 中无该用户记录时，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.history import history
    except ImportError:
        pytest.skip()
    import nonebot

    utils_session = make_mock_session()
    utils_session.scalar.return_value = make_mock_user(osu_id=114514)

    hist_session = make_mock_session()
    hist_session.scalar.return_value = None  # UserData 不存在
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    hist_session.scalars.return_value = scalars_result

    event = fake_group_message_event_v11(message=Message("/history"))

    with patch_session(UTILS_MODULE, utils_session):
        with (
            patch_session(HISTORY_MODULE, hist_session),
            patch(f"{HISTORY_MODULE}.merge_osutrack_history", new=AsyncMock(return_value=([], False))),
        ):
            async with app.test_matcher(history) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "没有找到 test_player 的历史数据"),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_history_success(app: App):
    """/history：有数据时调用 draw_history_plot 并回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.history import history
    except ImportError:
        pytest.skip()
    import base64
    import nonebot

    FAKE_IMG = b"FAKE_CHART"

    utils_session = make_mock_session()
    utils_session.scalar.return_value = make_mock_user(osu_id=114514, osu_name="testplayer")

    info1 = MagicMock()
    info1.pp = 1000.0
    info1.date = "2026-01-01"
    info1.g_rank = 10000
    info2 = MagicMock()
    info2.pp = 1050.0
    info2.date = "2026-01-08"
    info2.g_rank = 9500

    hist_session = make_mock_session()
    hist_session.scalar.return_value = make_mock_user(osu_name="testplayer")
    scalars_result = MagicMock()
    scalars_result.all.return_value = [info1, info2]
    hist_session.scalars.return_value = scalars_result

    event = fake_group_message_event_v11(message=Message("/history"))

    with patch_session(UTILS_MODULE, utils_session):
        with (
            patch_session(HISTORY_MODULE, hist_session),
            patch(
                f"{HISTORY_MODULE}.merge_osutrack_history",
                new=AsyncMock(
                    return_value=(
                        [(1000.0, "2026-01-01", 10000), (1050.0, "2026-01-08", 9500)],
                        False,
                    )
                ),
            ),
        ):
            with patch(f"{HISTORY_MODULE}.draw_history_plot", new=AsyncMock(return_value=FAKE_IMG)):
                async with app.test_matcher(history) as ctx:
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


@pytest.mark.asyncio
async def test_g0v0_history_is_rejected_without_reading_official_data(app: App):
    from nonebot_plugin_osubot.matcher.history import history

    import nonebot

    utils_session = make_mock_session()
    utils_session.scalar.side_effect = [None, make_mock_user(osu_id=408, osu_name="Chestnut")]
    event = fake_group_message_event_v11(message=Message("/history &gu"))

    with (
        patch_session(UTILS_MODULE, utils_session),
        patch(f"{HISTORY_MODULE}.get_session", side_effect=AssertionError("must not read official history")),
    ):
        async with app.test_matcher(history) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "g0v0 暂不提供 PP/排名历史数据，/hs 仅支持 osu! 官网"),
                result={"message_id": 1},
            )
            ctx.should_finished()


# ---------------------------------------------------------------------------
# url_match
# ---------------------------------------------------------------------------

URL_MODULE = "nonebot_plugin_osubot.matcher.url_match"


@pytest.mark.asyncio
async def test_url_match_draw_fails(app: App):
    """draw_map_info 抛异常时，handler 静默返回（不发消息）。"""
    try:
        from nonebot_plugin_osubot.matcher.url_match import url_match
    except ImportError:
        pytest.skip()
    import nonebot

    event = fake_group_message_event_v11(message=Message("https://osu.ppy.sh/beatmapsets/12345#osu/67890"))

    with patch(f"{URL_MODULE}.draw_map_info", new=AsyncMock(side_effect=Exception("fail"))):
        async with app.test_matcher(url_match) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            # 无任何 send，handler 直接 return


@pytest.mark.asyncio
async def test_url_match_success(app: App):
    """draw_map_info 成功时，发送图片与镜像站链接。"""
    try:
        from nonebot_plugin_osubot.matcher.url_match import url_match
    except ImportError:
        pytest.skip()
    import base64
    import nonebot

    FAKE_IMG = b"FAKE_MAP"

    event = fake_group_message_event_v11(message=Message("https://osu.ppy.sh/beatmapsets/12345#osu/67890"))
    expected_links = "镜像站1：https://catboy.best/d/12345\n镜像站2：https://osu.direct/api/d/12345\n小夜镜像站：https://txy1.sayobot.cn/beatmaps/download/novideo/12345"

    with patch(f"{URL_MODULE}.draw_map_info", new=AsyncMock(return_value=FAKE_IMG)):
        async with app.test_matcher(url_match) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message(
                    [
                        MessageSegment.reply(1),
                        MessageSegment.image(file=f"base64://{base64.b64encode(FAKE_IMG).decode()}"),
                        MessageSegment.text("\n" + expected_links),
                    ]
                ),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_direct_beatmap_url_is_resolved_and_remembered(app: App):
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, get_last_set_id
    from nonebot_plugin_osubot.matcher.url_match import url_match

    import nonebot

    event = fake_group_message_event_v11(message=Message("https://osu.ppy.sh/beatmaps/67890"))

    with patch(f"{URL_MODULE}.osu_api", new=AsyncMock(return_value={"beatmapset_id": 12345})):
        with patch(f"{URL_MODULE}.draw_map_info", new=AsyncMock(return_value=b"map")):
            async with app.test_matcher(url_match) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, ANY, result={"message_id": 1})
                ctx.should_finished()

    assert get_last_map_id(event) == "67890"
    assert await get_last_set_id(event) == "12345"


@pytest.mark.asyncio
async def test_beatmapset_url_is_remembered(app: App):
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, get_last_set_id
    from nonebot_plugin_osubot.matcher.url_match import url_match

    import nonebot

    event = fake_group_message_event_v11(message=Message("https://osu.ppy.sh/beatmapsets/12345"))

    with patch(f"{URL_MODULE}.draw_bmap_info", new=AsyncMock(return_value=b"set")):
        async with app.test_matcher(url_match) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, ANY, result={"message_id": 1})
            ctx.should_finished()

    assert get_last_map_id(event) is None
    assert await get_last_set_id(event) == "12345"


# ---------------------------------------------------------------------------
# /match
# ---------------------------------------------------------------------------

MATCH_MODULE = "nonebot_plugin_osubot.matcher.match"


@pytest.mark.asyncio
async def test_match_success(app: App):
    """/match <id>：调用 draw_match_history 并回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.match import match
    except ImportError:
        pytest.skip()
    import base64
    import nonebot

    FAKE_IMG = b"FAKE_MATCH"

    event = fake_group_message_event_v11(message=Message("/match 114514"))

    with patch(f"{MATCH_MODULE}.draw_match_history", new=AsyncMock(return_value=[FAKE_IMG])):
        async with app.test_matcher(match) as ctx:
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


@pytest.mark.asyncio
async def test_match_multiple_images_always_tries_forward(app: App):
    """多图发送不在 osubot 内部判断主号或分身。"""
    try:
        from nonebot_plugin_osubot.matcher.match import match
    except ImportError:
        pytest.skip()
    import nonebot

    pages = [b"PAGE_1", b"PAGE_2"]
    event = fake_group_message_event_v11(message=Message("/match 114514"))
    forward = AsyncMock(return_value=True)
    one_by_one = AsyncMock()

    with (
        patch(f"{MATCH_MODULE}.draw_match_history", new=AsyncMock(return_value=pages)),
        patch(f"{MATCH_MODULE}._send_forward", new=forward),
        patch(f"{MATCH_MODULE}._send_one_by_one", new=one_by_one),
    ):
        async with app.test_matcher(match) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter, self_id="1919810")
            ctx.receive_event(bot, event)

    forward.assert_awaited_once_with(bot, event, pages)
    one_by_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_match_send_retries_network_error_twice(app: App):
    match_module = importlib.import_module(MATCH_MODULE)

    operation = AsyncMock(side_effect=[match_module.NetworkError("first"), match_module.NetworkError("second"), "sent"])
    with patch(f"{MATCH_MODULE}.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await match_module._send_with_retry(operation)

    assert result == "sent"
    assert operation.await_count == 3
    assert sleep.await_count == 2


@pytest.mark.asyncio
async def test_match_forward_accepts_non_numeric_self_id(app: App):
    match_module = importlib.import_module(MATCH_MODULE)
    bot = MagicMock(self_id="bot-alpha")
    bot.call_api = AsyncMock(return_value={"message_id": 1})
    event = MagicMock(group_id=123, user_id=456)

    with patch(f"{MATCH_MODULE}._OB11_OK", True):
        sent = await match_module._send_forward(bot, event, [b"PAGE"])

    assert sent is True
    messages = bot.call_api.await_args.kwargs["messages"]
    assert messages[0]["data"]["user_id"] == "bot-alpha"


# ---------------------------------------------------------------------------
# /rating
# ---------------------------------------------------------------------------

RATING_MODULE = "nonebot_plugin_osubot.matcher.rating"


@pytest.mark.asyncio
async def test_rating_success(app: App):
    """/rating <arg>：调用 draw_rating 并回复图片。"""
    try:
        from nonebot_plugin_osubot.matcher.rating import rating
    except ImportError:
        pytest.skip()
    import base64
    import nonebot

    FAKE_IMG = b"FAKE_RATING"

    event = fake_group_message_event_v11(message=Message("/rating testuser"))

    with patch(f"{RATING_MODULE}.draw_rating", new=AsyncMock(return_value=FAKE_IMG)):
        async with app.test_matcher(rating) as ctx:
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
