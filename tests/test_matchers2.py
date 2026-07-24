"""Tests for remaining matchers: getbg, map/bmap, medal, bp/pfm, pr, preview, recommend, update, bp_analyze"""

import base64
import pytest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"


def text_msg(event, text: str) -> Message:
    return Message([MessageSegment.reply(event.message_id), MessageSegment.text(text)])


def img_msg(event, raw: bytes) -> Message:
    return Message(
        [
            MessageSegment.reply(event.message_id),
            MessageSegment.image(file=f"base64://{base64.b64encode(raw).decode()}"),
        ]
    )


# ============================================================
# getbg
# ============================================================

GETBG_MODULE = "nonebot_plugin_osubot.matcher.getbg"


@pytest.mark.asyncio
async def test_getbg_no_input(app: App):
    """/getbg 无参数 → 提示输入地图ID"""
    try:
        from nonebot_plugin_osubot.matcher.getbg import getbg
    except ImportError:
        pytest.skip()

    event = fake_group_message_event_v11(message=Message("/getbg"))

    async with app.test_matcher(getbg) as ctx:
        adapter = nonebot.get_adapter(OnebotV11Adapter)
        bot = ctx.create_bot(base=Bot, adapter=adapter)
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            text_msg(event, "请输入需要提取BG的地图ID，或先查询一张谱面"),
            result={"message_id": 1},
        )
        ctx.should_finished()


@pytest.mark.asyncio
async def test_getbg_network_error(app: App):
    """/getbg <id> 网络错误 → 回复错误信息"""
    try:
        from nonebot_plugin_osubot.matcher.getbg import getbg
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip()

    event = fake_group_message_event_v11(message=Message("/getbg 114514"))

    with patch(f"{GETBG_MODULE}.get_bg", new=AsyncMock(side_effect=NetworkError("连接超时"))):
        async with app.test_matcher(getbg) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, text_msg(event, "获取图片时 连接超时"), result={"message_id": 1})
            ctx.should_finished()


@pytest.mark.asyncio
async def test_getbg_success(app: App):
    """/getbg <id> 成功 → 发送图片"""
    try:
        from nonebot_plugin_osubot.matcher.getbg import getbg
    except ImportError:
        pytest.skip()

    fake_img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    byt = BytesIO()
    fake_img.convert("RGB").save(byt, "jpeg")
    expected_bytes = byt.getvalue()

    event = fake_group_message_event_v11(message=Message("/getbg 114514"))

    with patch(f"{GETBG_MODULE}.get_bg", new=AsyncMock(return_value=fake_img)):
        async with app.test_matcher(getbg) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, img_msg(event, expected_bytes), result={"message_id": 1})
            ctx.should_finished()


# ============================================================
# map / bmap
# ============================================================

MAP_MODULE = "nonebot_plugin_osubot.matcher.map"
FAKE_MAP_IMG = b"FAKE_MAP_IMAGE"


@pytest.mark.asyncio
async def test_osu_map_no_target(app: App):
    """/map 无目标 → 提示输入地图ID"""
    try:
        from nonebot_plugin_osubot.matcher.map import osu_map
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/map"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(osu_map) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "请输入地图ID，或先查询一张谱面"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_osu_map_network_error(app: App):
    """/map <id> 网络错误 → 回复错误信息"""
    try:
        from nonebot_plugin_osubot.matcher.map import osu_map
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/map 12345"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{MAP_MODULE}.draw_map_info", new=AsyncMock(side_effect=NetworkError("超时"))):
            async with app.test_matcher(osu_map) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "在查找地图mapid:12345时 超时"),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_osu_map_success(app: App):
    """/map <id> 成功 → 发送图片"""
    try:
        from nonebot_plugin_osubot.matcher.map import osu_map
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/map 12345"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{MAP_MODULE}.draw_map_info", new=AsyncMock(return_value=FAKE_MAP_IMG)):
            async with app.test_matcher(osu_map) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_MAP_IMG), result={"message_id": 1})
                ctx.should_finished()


@pytest.mark.asyncio
async def test_osu_map_accepts_beatmap_url(app: App):
    from nonebot_plugin_osubot.matcher.map import osu_map

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)
    event = fake_group_message_event_v11(message=Message("/m https://osu.ppy.sh/beatmapsets/12345#mania/67890"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{MAP_MODULE}.draw_map_info", new=AsyncMock(return_value=FAKE_MAP_IMG)) as draw:
            async with app.test_matcher(osu_map) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_MAP_IMG), result={"message_id": 1})
                ctx.should_finished()

    assert draw.call_args.args[0] == "67890"


@pytest.mark.asyncio
async def test_bmap_no_target(app: App):
    """/bmap 无目标 → 提示输入setID"""
    try:
        from nonebot_plugin_osubot.matcher.map import bmap
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/bmap"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(bmap) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "请输入setID，或先查询一张谱面"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_bmap_success(app: App):
    """/bmap <id> 成功 → 发送图片"""
    try:
        from nonebot_plugin_osubot.matcher.map import bmap
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/bmap 12345"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{MAP_MODULE}.draw_bmap_info", new=AsyncMock(return_value=FAKE_MAP_IMG)):
            async with app.test_matcher(bmap) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_MAP_IMG), result={"message_id": 1})
                ctx.should_finished()


# ============================================================
# medal
# ============================================================

MEDAL_MODULE = "nonebot_plugin_osubot.matcher.medal"


@pytest.mark.asyncio
async def test_medal_not_found(app: App):
    """/medal 未找到 → 提示名字打错了"""
    try:
        from nonebot_plugin_osubot.matcher.medal import medal
    except ImportError:
        pytest.skip()

    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "not found"}  # no "MedalID"

    event = fake_group_message_event_v11(message=Message("/medal Nonexistent"))

    with patch(f"{MEDAL_MODULE}.safe_async_get", new=AsyncMock(return_value=mock_response)):
        async with app.test_matcher(medal) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(event, "没有找到欸，看看是不是名字打错了", result={"message_id": 1})
            ctx.should_finished()


# ============================================================
# bp / pfm
# ============================================================

BP_MODULE = "nonebot_plugin_osubot.matcher.bp"
FAKE_BP_IMG = b"FAKE_BP_IMAGE"


@pytest.mark.asyncio
async def test_bp_error_not_bound(app: App):
    """/bp 未绑定 → 回复绑定提示"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/bp"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(bp) as ctx:
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
async def test_bp_out_of_range(app: App):
    """/bp 201 超过范围 → 提示只允许 1-200"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/bp 201"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(bp) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "只允许查询bp 1-200 的成绩"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_bp_success(app: App):
    """/bp 1 成功 → 发送图片"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/bp 1"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_score", new=AsyncMock(return_value=(FAKE_BP_IMG, 24680, 13579))):
            async with app.test_matcher(bp) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_BP_IMG), result={"message_id": 1})
                ctx.should_finished()


@pytest.mark.asyncio
async def test_bp_network_error(app: App):
    """/bp 1 网络错误 → 回复错误信息"""
    try:
        from nonebot_plugin_osubot.matcher.bp import bp
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_name="testuser", lazer_mode=False)

    event = fake_group_message_event_v11(message=Message("/bp 1"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_score", new=AsyncMock(side_effect=NetworkError("超时"))):
            async with app.test_matcher(bp) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "在查找用户：testuser osu模式 bp1 stable模式下时 超时"),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_pfm_reversed_range_is_normalized(app: App):
    """/pfm 200-1 is normalized to 1-200."""
    try:
        from nonebot_plugin_osubot.matcher.bp import pfm
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/pfm 200-1"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_bp", new=AsyncMock(return_value=FAKE_BP_IMG)) as draw:
            async with app.test_matcher(pfm) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_BP_IMG), result={"message_id": 1})
                ctx.should_finished()

    assert draw.call_args.args[5:7] == (1, 200)


@pytest.mark.asyncio
async def test_pfm_success(app: App):
    """/pfm 成功 → 发送图片"""
    try:
        from nonebot_plugin_osubot.matcher.bp import pfm
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/pfm 1-50"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{BP_MODULE}.draw_bp", new=AsyncMock(return_value=FAKE_BP_IMG)):
            async with app.test_matcher(pfm) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_BP_IMG), result={"message_id": 1})
                ctx.should_finished()


# ============================================================
# pr
# ============================================================

PR_MODULE = "nonebot_plugin_osubot.matcher.pr"
FAKE_PR_IMG = b"FAKE_PR_IMAGE"


@pytest.mark.asyncio
async def test_pr_error_not_bound(app: App):
    """/pr 未绑定 → 回复绑定提示"""
    try:
        from nonebot_plugin_osubot.matcher.pr import pr
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/pr"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(pr) as ctx:
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
async def test_pr_success(app: App):
    """/pr 成功 → 发送图片"""
    try:
        from nonebot_plugin_osubot.matcher.pr import pr
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/pr"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{PR_MODULE}.draw_score", new=AsyncMock(return_value=(FAKE_PR_IMG, 24680, 13579))):
            async with app.test_matcher(pr) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_PR_IMG), result={"message_id": 1})
                ctx.should_finished()

    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, get_last_set_id

    assert get_last_map_id(event) == "24680"
    assert await get_last_set_id(event) == "13579"


@pytest.mark.asyncio
async def test_recent_success_remembers_map(app: App):
    """/re records the beatmap returned by the selected recent score."""
    from nonebot_plugin_osubot.matcher.pr import recent
    from nonebot_plugin_osubot.matcher.map_context import get_last_map_id, get_last_set_id

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)
    event = fake_group_message_event_v11(message=Message("/re"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{PR_MODULE}.draw_score", new=AsyncMock(return_value=(FAKE_PR_IMG, 97531, 86420))):
            async with app.test_matcher(recent) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, img_msg(event, FAKE_PR_IMG), result={"message_id": 1})
                ctx.should_finished()

    assert get_last_map_id(event) == "97531"
    assert await get_last_set_id(event) == "86420"


@pytest.mark.asyncio
async def test_pr_network_error(app: App):
    """/pr 网络错误 → 回复错误信息"""
    try:
        from nonebot_plugin_osubot.matcher.pr import pr
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_name="testuser", lazer_mode=False)

    event = fake_group_message_event_v11(message=Message("/pr"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{PR_MODULE}.draw_score", new=AsyncMock(side_effect=NetworkError("超时"))):
            async with app.test_matcher(pr) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "在查找用户：testuser osu模式 stable模式下 最近第1个成绩时 超时"),
                    result={"message_id": 1},
                )
                ctx.should_finished()


# ============================================================
# preview
# ============================================================

PREVIEW_MODULE = "nonebot_plugin_osubot.matcher.preview"


@pytest.mark.asyncio
async def test_preview_no_target(app: App):
    """/预览 无参数 → 提示输入mapID"""
    try:
        from nonebot_plugin_osubot.matcher.preview import generate_preview
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/预览"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(generate_preview) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "请输入正确的地图mapID，或先查询一张谱面"),
                result={"message_id": 1},
            )
            ctx.should_finished()


@pytest.mark.asyncio
async def test_preview_network_error(app: App):
    """/预览 <id> 网络错误 → 回复错误信息"""
    try:
        from nonebot_plugin_osubot.matcher.preview import generate_preview
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    event = fake_group_message_event_v11(message=Message("/预览 12345"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{PREVIEW_MODULE}.osu_api", new=AsyncMock(side_effect=NetworkError("超时"))):
            async with app.test_matcher(generate_preview) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "查找map_id:12345 信息时 超时"),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_preview_ctb_gif_param_uses_osu_preview_gif(app: App):
    """/预览 <id> +gif 在 ctb 模式下使用 osu_preview GIF。"""
    try:
        from nonebot_plugin_osubot.matcher.preview import generate_preview
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_mode=2)

    event = fake_group_message_event_v11(message=Message("/预览 12345 +gif"))

    with patch_session(UTILS_MODULE, session):
        with patch(
            f"{PREVIEW_MODULE}.osu_api",
            new=AsyncMock(return_value={"beatmapset_id": 67890, "mode_int": 0}),
        ):
            with patch(f"{PREVIEW_MODULE}.draw_osu_preview", new=AsyncMock(return_value=b"gif")) as draw:
                async with app.test_matcher(generate_preview) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        img_msg(event, b"gif"),
                        result={"message_id": 1},
                    )
                    ctx.should_finished()

                draw.assert_awaited_once_with(12345, 67890, False)


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["/视频预览 12345", "/vp 12345"])
async def test_full_preview_gif_param_sends_cached_video(app: App, tmp_path, command):
    """/视频预览 <id> 在 mania 模式直接使用分段合成后的 MP4。"""
    try:
        from nonebot_plugin_osubot.matcher.preview import generate_preview
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_mode=3)
    video = tmp_path / "preview.mp4"
    video.write_bytes(b"video")
    event = fake_group_message_event_v11(message=Message(command))

    async def render_full_preview(beatmap_id, beatmapset_id, progress_callback):
        await progress_callback(65)
        return video

    with patch_session(UTILS_MODULE, session):
        with patch(
            f"{PREVIEW_MODULE}.osu_api",
            new=AsyncMock(return_value={"beatmapset_id": 67890, "mode_int": 3}),
        ):
            with patch(
                f"{PREVIEW_MODULE}.draw_full_osu_preview",
                new=AsyncMock(side_effect=render_full_preview),
            ) as draw:
                async with app.test_matcher(generate_preview) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        text_msg(event, "正在生成完整预览，预计还需约1分10秒，请稍候…"),
                        result={"message_id": 1},
                    )
                    ctx.should_call_send(
                        event,
                        Message(MessageSegment.video(file=video.read_bytes())),
                        result={"message_id": 1},
                    )
                    ctx.should_finished()

                draw.assert_awaited_once()
                assert draw.await_args.args == (12345, 67890)
                assert callable(draw.await_args.kwargs["progress_callback"])


@pytest.mark.asyncio
async def test_full_preview_without_gif_keeps_mania_image(app: App, tmp_path):
    """/完整预览 <id> 不带 +gif 时保留 Mania 完整图片。"""
    try:
        from nonebot_plugin_osubot.matcher.preview import generate_preview
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_mode=3)
    osu_file = tmp_path / "map.osu"
    osu_file.write_text("osu file format v14", encoding="utf-8")
    event = fake_group_message_event_v11(message=Message("/完整预览 12345"))

    with patch_session(UTILS_MODULE, session):
        with patch(
            f"{PREVIEW_MODULE}.osu_api",
            new=AsyncMock(return_value={"beatmapset_id": 67890, "mode_int": 3}),
        ):
            with patch(f"{PREVIEW_MODULE}.download_osu", new=AsyncMock(return_value=osu_file)):
                with patch(
                    f"{PREVIEW_MODULE}.generate_preview_pic",
                    new=AsyncMock(return_value=b"full-image"),
                ) as draw:
                    async with app.test_matcher(generate_preview) as ctx:
                        adapter = nonebot.get_adapter(OnebotV11Adapter)
                        bot = ctx.create_bot(base=Bot, adapter=adapter)
                        ctx.receive_event(bot, event)
                        ctx.should_call_send(
                            event,
                            img_msg(event, b"full-image"),
                            result={"message_id": 1},
                        )
                        ctx.should_finished()

                    draw.assert_awaited_once_with(osu_file, True)


# ============================================================
# recommend
# ============================================================

RECOMMEND_MODULE = "nonebot_plugin_osubot.matcher.recommend"


@pytest.mark.asyncio
async def test_recommend_error_not_bound(app: App):
    """/recommend 未绑定 → 回复绑定提示"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/recommend"))

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


@pytest.mark.asyncio
async def test_recommend_taiko_mode(app: App):
    """/recommend taiko模式 → 正常返回推荐"""
    try:
        from nonebot_plugin_osubot.matcher.recommend import recommend
        from nonebot_plugin_osubot.schema.alphaosu import RecommendData
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_mode=1)  # taiko

    recommend_data = RecommendData(player_id=114514, mode="taiko", recommendations=[])

    event = fake_group_message_event_v11(message=Message("/recommend"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{RECOMMEND_MODULE}.get_recommend", new=AsyncMock(return_value=recommend_data)):
            async with app.test_matcher(recommend) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "暂时没有找到可推荐的谱面，已加入更新队列\n请明天再来查看推荐吧"),
                    result={"message_id": 1},
                )


# ============================================================
# update_info / clear_background
# ============================================================

UPDATE_MODULE = "nonebot_plugin_osubot.matcher.update"


@pytest.mark.asyncio
async def test_update_info_error_not_bound(app: App):
    """/update 未绑定 → 回复绑定提示并返回"""
    try:
        from nonebot_plugin_osubot.matcher.update import update_info
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/update"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(update_info) as ctx:
            adapter = nonebot.get_adapter(OnebotV11Adapter)
            bot = ctx.create_bot(base=Bot, adapter=adapter)
            ctx.receive_event(bot, event)
            ctx.should_call_send(
                event,
                text_msg(event, "该账号尚未绑定，请输入 /bind 用户名 绑定账号"),
                result={"message_id": 1},
            )


@pytest.mark.asyncio
async def test_update_info_success(app: App):
    """/update 成功 → 回复更新成功（无图标缓存文件）"""
    try:
        from nonebot_plugin_osubot.matcher.update import update_info
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    mock_user_dir = MagicMock()
    mock_user_dir.glob.return_value = []
    mock_cache_path = MagicMock()
    mock_cache_path.__truediv__ = MagicMock(return_value=mock_user_dir)

    event = fake_group_message_event_v11(message=Message("/update"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{UPDATE_MODULE}.user_cache_path", mock_cache_path):
            async with app.test_matcher(update_info) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, text_msg(event, "个人信息更新成功"), result={"message_id": 1})


@pytest.mark.asyncio
async def test_clear_background_no_file(app: App):
    """/清空背景 文件不存在 → 提示还没有设置背景"""
    try:
        from nonebot_plugin_osubot.matcher.update import clear_background
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    mock_info_path = MagicMock()
    mock_info_path.exists.return_value = False
    mock_user_dir = MagicMock()
    mock_user_dir.__truediv__ = MagicMock(return_value=mock_info_path)
    mock_cache_path = MagicMock()
    mock_cache_path.__truediv__ = MagicMock(return_value=mock_user_dir)

    event = fake_group_message_event_v11(message=Message("/清空背景"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{UPDATE_MODULE}.user_cache_path", mock_cache_path):
            async with app.test_matcher(clear_background) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "您还没有设置背景或已成功清除背景"),
                    result={"message_id": 1},
                )


@pytest.mark.asyncio
async def test_clear_background_success(app: App):
    """/清空背景 文件存在 → 删除并回复成功"""
    try:
        from nonebot_plugin_osubot.matcher.update import clear_background
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514)

    mock_info_path = MagicMock()
    mock_info_path.exists.return_value = True
    mock_info_path.unlink = MagicMock()
    mock_user_dir = MagicMock()
    mock_user_dir.__truediv__ = MagicMock(return_value=mock_info_path)
    mock_cache_path = MagicMock()
    mock_cache_path.__truediv__ = MagicMock(return_value=mock_user_dir)

    event = fake_group_message_event_v11(message=Message("/清空背景"))

    with patch_session(UTILS_MODULE, session):
        with patch(f"{UPDATE_MODULE}.user_cache_path", mock_cache_path):
            async with app.test_matcher(clear_background) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, text_msg(event, "背景图片清除成功"), result={"message_id": 1})


# ============================================================
# bp_analyze
# ============================================================

BPA_MODULE = "nonebot_plugin_osubot.matcher.bp_analyze"
FAKE_BPA_IMG = b"FAKE_BPA_IMAGE"
FAKE_BPA_DATA = {
    "pp_ls": [300.0],
    "length_ls": [{"value": 120.0, "itemStyle": {"color": "#84d61c"}}],
    "star_scatter": [{"name": "A", "color": "#84d61c", "data": [[6.0, 300.0]]}],
    "mod_pp_ls": [{"name": "NM", "value": 285.0}],
    "mapper_pp_ls": [{"name": "mapper_name", "value": 285.0}],
    "stats": {
        "weighted_pp": 285.0,
        "total_pp": 300.0,
        "bp_count": 1,
        "avg_acc": 98.5,
        "avg_stars": 6.0,
        "avg_bpm": 200.0,
        "top_mod": "NM",
        "top_mapper": "mapper_name",
    },
}


@pytest.mark.asyncio
async def test_bpa_error_not_bound(app: App):
    """/bpa 未绑定 → 回复绑定提示"""
    try:
        from nonebot_plugin_osubot.matcher.bp_analyze import bp_analyze
    except ImportError:
        pytest.skip()

    session = make_mock_session()
    session.scalar.return_value = None

    event = fake_group_message_event_v11(message=Message("/bpa"))

    with patch_session(UTILS_MODULE, session):
        async with app.test_matcher(bp_analyze) as ctx:
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
async def test_bpa_network_error(app: App):
    """/bpa 网络错误 → 回复错误信息"""
    try:
        from nonebot_plugin_osubot.matcher.bp_analyze import bp_analyze
        from nonebot_plugin_osubot.exceptions import NetworkError
    except ImportError:
        pytest.skip()

    utils_session = make_mock_session()
    utils_session.scalar.return_value = make_mock_user(osu_id=114514, osu_name="testuser", lazer_mode=False)

    bpa_session = make_mock_session()
    bpa_session.scalar.return_value = make_mock_user(osu_id=114514, lazer_mode=False)

    event = fake_group_message_event_v11(message=Message("/bpa"))

    with patch_session(UTILS_MODULE, utils_session):
        with patch_session(BPA_MODULE, bpa_session):
            with patch(f"{BPA_MODULE}.get_user_scores", new=AsyncMock(side_effect=NetworkError("超时"))):
                async with app.test_matcher(bp_analyze) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        text_msg(event, "在查找用户：testuser osu模式 stable模式下时 超时"),
                        result={"message_id": 1},
                    )
                    ctx.should_finished()


@pytest.mark.asyncio
async def test_bpa_success(app: App):
    """/bpa 成功 → 发送分析图"""
    try:
        from nonebot_plugin_osubot.matcher.bp_analyze import bp_analyze
    except ImportError:
        pytest.skip()

    utils_session = make_mock_session()
    utils_session.scalar.return_value = make_mock_user(osu_id=114514, osu_name="testuser", lazer_mode=False)

    bpa_user = make_mock_user(osu_id=114514, lazer_mode=False)
    bpa_session = make_mock_session()
    bpa_session.scalar.return_value = bpa_user

    mock_score = MagicMock()
    mock_score.mods = []
    mock_score.rank = "A"
    mock_score.pp = 300.0
    mock_score.beatmap = MagicMock()
    mock_score.beatmap.total_length = 120.0
    mock_score.beatmap.user_id = 99999
    mock_score.beatmap.creator = "mapper_name"

    def fake_cal(lazer_mode, score):
        score.pp = 300.0
        score.rank = "A"
        return score

    event = fake_group_message_event_v11(message=Message("/bpa"))

    with patch_session(UTILS_MODULE, utils_session):
        with patch_session(BPA_MODULE, bpa_session):
            with patch(f"{BPA_MODULE}.get_user_scores", new=AsyncMock(return_value=[mock_score])):
                with patch(f"{BPA_MODULE}.cal_score_info", side_effect=fake_cal):
                    with patch(f"{BPA_MODULE}.build_bpa_data", new=AsyncMock(return_value=FAKE_BPA_DATA)):
                        with patch(f"{BPA_MODULE}.draw_bpa_plot", new=AsyncMock(return_value=FAKE_BPA_IMG)):
                            async with app.test_matcher(bp_analyze) as ctx:
                                adapter = nonebot.get_adapter(OnebotV11Adapter)
                                bot = ctx.create_bot(base=Bot, adapter=adapter)
                                ctx.receive_event(bot, event)
                                ctx.should_call_send(event, img_msg(event, FAKE_BPA_IMG), result={"message_id": 1})
                                ctx.should_finished()
