"""简单 matcher 测试：mu / osu_help / history / url_match / match / rating"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
            Message([MessageSegment.reply(1), MessageSegment.image(file=f"base64://{__import__('base64').b64encode(img1).decode()}")]),
            result={"message_id": 1},
        )
        ctx.should_finished()


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
            Message([MessageSegment.reply(1), MessageSegment.image(file=f"base64://{__import__('base64').b64encode(img2).decode()}")]),
            result={"message_id": 1},
        )
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

    event = fake_group_message_event_v11(message=Message("/history"))

    with patch_session(UTILS_MODULE, utils_session):
        with patch_session(HISTORY_MODULE, hist_session):
            async with app.test_matcher(history) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "没有114514的数据哦"),
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

    info1 = MagicMock(); info1.pp = 1000.0; info1.date = "2026-01-01"; info1.g_rank = 10000
    info2 = MagicMock(); info2.pp = 1050.0; info2.date = "2026-01-08"; info2.g_rank = 9500

    hist_session = make_mock_session()
    hist_session.scalar.return_value = make_mock_user(osu_name="testplayer")
    scalars_result = MagicMock()
    scalars_result.all.return_value = [info1, info2]
    hist_session.scalars.return_value = scalars_result

    event = fake_group_message_event_v11(message=Message("/history"))

    with patch_session(UTILS_MODULE, utils_session):
        with patch_session(HISTORY_MODULE, hist_session):
            with patch(f"{HISTORY_MODULE}.draw_history_plot", new=AsyncMock(return_value=FAKE_IMG)):
                async with app.test_matcher(history) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        Message([
                            MessageSegment.reply(1),
                            MessageSegment.image(file=f"base64://{base64.b64encode(FAKE_IMG).decode()}"),
                        ]),
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

    event = fake_group_message_event_v11(
        message=Message("https://osu.ppy.sh/beatmapsets/12345#osu/67890")
    )

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

    event = fake_group_message_event_v11(
        message=Message("https://osu.ppy.sh/beatmapsets/12345#osu/67890")
    )
    expected_links = "镜像站1：https://catboy.best/d/12345\n镜像站2：https://osu.direct/api/d/12345\n小夜镜像站：https://txy1.sayobot.cn/beatmaps/download/novideo/12345"

    with patch(f"{URL_MODULE}.draw_map_info", new=AsyncMock(return_value=FAKE_IMG)):
        async with app.test_matcher(url_match) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([
                    MessageSegment.reply(1),
                    MessageSegment.image(file=f"base64://{base64.b64encode(FAKE_IMG).decode()}"),
                    MessageSegment.text("\n" + expected_links),
                ]),
                result={"message_id": 1},
            )
            ctx.should_finished()


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

    with patch(f"{MATCH_MODULE}.draw_match_history", new=AsyncMock(return_value=FAKE_IMG)):
        async with app.test_matcher(match) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                Message([
                    MessageSegment.reply(1),
                    MessageSegment.image(file=f"base64://{base64.b64encode(FAKE_IMG).decode()}"),
                ]),
                result={"message_id": 1},
            )
            ctx.should_finished()


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
                Message([
                    MessageSegment.reply(1),
                    MessageSegment.image(file=f"base64://{base64.b64encode(FAKE_IMG).decode()}"),
                ]),
                result={"message_id": 1},
            )
            ctx.should_finished()
