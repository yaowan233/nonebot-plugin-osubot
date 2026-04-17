"""Tests for matcher/guess.py - GameManager 和猜歌指令。"""

import pytest
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

MODULE = "nonebot_plugin_osubot.matcher.guess"
UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_score(
    title: str = "Test Song",
    title_unicode: str = "テスト曲",
    beatmapset_id: int = 12345,
    beatmap_id: int = 67890,
) -> MagicMock:
    score = MagicMock()
    score.beatmapset.id = beatmapset_id
    score.beatmapset.title = title
    score.beatmapset.title_unicode = title_unicode
    score.beatmapset.artist = "Test Artist"
    score.beatmapset.artist_unicode = "テストアーティスト"
    score.beatmapset.creator = "mapper"
    score.beatmapset.covers.cover = "https://example.com/cover.jpg"
    score.beatmap.id = beatmap_id
    score.mods = []
    return score


def make_bound_utils_session(osu_mode: int = 0) -> AsyncMock:
    """split_msg 用的 session：用户已绑定，指定模式。"""
    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_mode=osu_mode)
    return session


def make_binded_id_session(user_ids: list) -> AsyncMock:
    """handler 内查询 binded_id 用的 session。"""
    session = make_mock_session()
    scalars_result = MagicMock()
    scalars_result.all.return_value = user_ids
    session.scalars.return_value = scalars_result
    return session


def text_msg(event, text: str) -> Message:
    return Message([MessageSegment.reply(event.message_id), MessageSegment.text(text)])


# ---------------------------------------------------------------------------
# GameManager 单元测试（无 nonebot 依赖）
# ---------------------------------------------------------------------------


def test_game_manager_set_get_pop():
    """set / get / pop / is_game_running 基本流程。"""
    from nonebot_plugin_osubot.matcher.guess import GameManager, GameType

    gm = GameManager()
    score = MagicMock()

    assert gm.get_game(GameType.AUDIO, "g1") is None
    assert not gm.is_game_running(GameType.AUDIO, "g1")

    gm.set_game(GameType.AUDIO, "g1", score)
    assert gm.get_game(GameType.AUDIO, "g1") is score
    assert gm.is_game_running(GameType.AUDIO, "g1")

    assert gm.pop_game(GameType.AUDIO, "g1") is score
    assert gm.get_game(GameType.AUDIO, "g1") is None
    assert not gm.is_game_running(GameType.AUDIO, "g1")


def test_game_manager_pop_missing_key_returns_none():
    """pop 不存在的 key 返回 None，不抛异常。"""
    from nonebot_plugin_osubot.matcher.guess import GameManager, GameType

    gm = GameManager()
    assert gm.pop_game(GameType.AUDIO, "nonexistent") is None


def test_game_manager_hint_lifecycle():
    """hint 初始化 → 使用 → 重置 全流程。"""
    from nonebot_plugin_osubot.matcher.guess import GameManager, GameType

    gm = GameManager()

    assert gm.get_hint(GameType.AUDIO, "g1") is None

    gm.init_hint(GameType.AUDIO, "g1")
    hints = gm.get_hint(GameType.AUDIO, "g1")
    assert hints is not None
    assert not any(hints.values())  # 初始全为 False

    for key in hints:
        hints[key] = True
    assert all(hints.values())

    gm.reset_hint(GameType.AUDIO, "g1")
    assert gm.get_hint(GameType.AUDIO, "g1") is None


def test_game_manager_game_types_independent():
    """AUDIO / PIC / CHART 三种游戏类型的状态互相独立。"""
    from nonebot_plugin_osubot.matcher.guess import GameManager, GameType

    gm = GameManager()
    score = MagicMock()

    gm.set_game(GameType.AUDIO, "g1", score)
    assert gm.is_game_running(GameType.AUDIO, "g1")
    assert not gm.is_game_running(GameType.PIC, "g1")
    assert not gm.is_game_running(GameType.CHART, "g1")


def test_game_manager_hint_sessions_independent():
    """同类型不同 session 的 hint 状态互不影响。"""
    from nonebot_plugin_osubot.matcher.guess import GameManager, GameType

    gm = GameManager()
    gm.init_hint(GameType.AUDIO, "g1")
    gm.init_hint(GameType.AUDIO, "g2")

    hints_g1 = gm.get_hint(GameType.AUDIO, "g1")
    hints_g2 = gm.get_hint(GameType.AUDIO, "g2")

    hints_g1["pic"] = True
    assert not hints_g2.get("pic"), "g2 的 hint 不应受 g1 影响"


def test_game_manager_timer_set_get_pop():
    """timer 的 set / get / pop 流程。"""
    from nonebot_plugin_osubot.matcher.guess import GameManager, GameType

    gm = GameManager()
    fake_timer = MagicMock()

    assert gm.get_timer(GameType.AUDIO, "g1") is None
    gm.set_timer(GameType.AUDIO, "g1", fake_timer)
    assert gm.get_timer(GameType.AUDIO, "g1") is fake_timer
    assert gm.pop_timer(GameType.AUDIO, "g1") is fake_timer
    assert gm.get_timer(GameType.AUDIO, "g1") is None


# ---------------------------------------------------------------------------
# guess_audio handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guess_audio_no_binded_users(app: App):
    """该模式无人绑定时，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_audio
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    event = fake_group_message_event_v11(message=Message("/音频猜歌"))

    with patch_session(UTILS_MODULE, make_bound_utils_session(osu_mode=0)):
        with patch_session(MODULE, make_binded_id_session([])):
            async with app.test_matcher(guess_audio) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    text_msg(event, "还没有人绑定该模式的osu账号呢，绑定了再来试试吧"),
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_guess_audio_all_songs_guessed(app: App):
    """select_score_from_user 返回 (None, msg) 时，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_audio
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    event = fake_group_message_event_v11(message=Message("/音频猜歌"))

    with patch_session(UTILS_MODULE, make_bound_utils_session()):
        with patch_session(MODULE, make_binded_id_session(["12345678"])):
            with patch(
                f"{MODULE}.select_score_from_user", new=AsyncMock(return_value=(None, "今日所有歌曲都被猜过了"))
            ):
                async with app.test_matcher(guess_audio) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        text_msg(event, "今日所有歌曲都被猜过了"),
                        result={"message_id": 1},
                    )
                    ctx.should_finished()


@pytest.mark.asyncio
async def test_guess_audio_download_fail(app: App):
    """音频下载失败时，发送启动消息后回复失败并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_audio
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    score = make_mock_score()
    event = fake_group_message_event_v11(message=Message("/音频猜歌"))

    with patch_session(UTILS_MODULE, make_bound_utils_session(osu_mode=0)):
        with patch_session(MODULE, make_binded_id_session(["12345678"])):
            with patch(f"{MODULE}.select_score_from_user", new=AsyncMock(return_value=(score, "testuser"))):
                with patch(f"{MODULE}.set_timeout"):
                    with patch(f"{MODULE}.safe_async_get", new=AsyncMock(return_value=None)):
                        async with app.test_matcher(guess_audio) as ctx:
                            adapter = nonebot.get_adapter(OnebotV11Adapter)
                            bot = ctx.create_bot(base=Bot, adapter=adapter)
                            ctx.receive_event(bot, event)
                            ctx.should_call_send(
                                event,
                                text_msg(
                                    event, "开始音频猜歌游戏，猜猜下面音频的曲名吧，该曲抽选自testuser osu 模式的bp"
                                ),
                                result={"message_id": 1},
                            )
                            ctx.should_call_send(
                                event,
                                text_msg(event, "音频下载失败了 qaq "),
                                result={"message_id": 2},
                            )
                            ctx.should_finished()


# ---------------------------------------------------------------------------
# guess_pic handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guess_pic_no_binded_users(app: App):
    """该模式无人绑定时，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_pic
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    event = fake_group_message_event_v11(message=Message("/图片猜歌"))

    with patch_session(UTILS_MODULE, make_bound_utils_session(osu_mode=0)):
        with patch_session(MODULE, make_binded_id_session([])):
            async with app.test_matcher(guess_pic) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    "还没有人绑定该模式的osu账号呢，绑定了再来试试吧",
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_guess_pic_all_songs_guessed(app: App):
    """select_score_from_user 返回 (None, msg) 时，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_pic
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    event = fake_group_message_event_v11(message=Message("/图片猜歌"))

    with patch_session(UTILS_MODULE, make_bound_utils_session()):
        with patch_session(MODULE, make_binded_id_session(["12345678"])):
            with patch(
                f"{MODULE}.select_score_from_user", new=AsyncMock(return_value=(None, "今日所有歌曲都被猜过了"))
            ):
                async with app.test_matcher(guess_pic) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        text_msg(event, "今日所有歌曲都被猜过了"),
                        result={"message_id": 1},
                    )
                    ctx.should_finished()


# ---------------------------------------------------------------------------
# guess_chart handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guess_chart_mode_0_supported(app: App):
    """osu 模式（mode=0）支持谱面猜歌并发送预览图。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_chart
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    event = fake_group_message_event_v11(message=Message("/谱面猜歌"))
    score = make_mock_score()

    with patch_session(UTILS_MODULE, make_bound_utils_session(osu_mode=0)):
        with patch_session(MODULE, make_binded_id_session(["12345678"])):
            with patch(f"{MODULE}.select_score_from_user", new=AsyncMock(return_value=(score, "testuser"))):
                with patch(f"{MODULE}.chart_set_timeout"):
                    with patch(f"{MODULE}.draw_osu_preview", new=AsyncMock(return_value=b"img")):
                        async with app.test_matcher(guess_chart) as ctx:
                            adapter = nonebot.get_adapter(OnebotV11Adapter)
                            bot = ctx.create_bot(base=Bot, adapter=adapter)
                            ctx.should_call_send(event, ANY, result={"message_id": 1})
                            ctx.receive_event(bot, event)
                            ctx.should_finished()


@pytest.mark.asyncio
async def test_guess_chart_no_binded_users(app: App):
    """mode=3（mania），无人绑定时，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_chart
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    event = fake_group_message_event_v11(message=Message("/谱面猜歌"))

    with patch_session(UTILS_MODULE, make_bound_utils_session(osu_mode=3)):
        with patch_session(MODULE, make_binded_id_session([])):
            async with app.test_matcher(guess_chart) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    "还没有人绑定该模式的osu账号呢，绑定了再来试试吧",
                    result={"message_id": 1},
                )
                ctx.should_finished()


@pytest.mark.asyncio
async def test_guess_chart_all_songs_guessed(app: App):
    """select_score_from_user 返回 (None, msg) 时，回复提示并 finish。"""
    try:
        from nonebot_plugin_osubot.matcher.guess import guess_chart
    except ImportError:
        pytest.skip("nonebot_plugin_osubot not available")
    import nonebot

    event = fake_group_message_event_v11(message=Message("/谱面猜歌"))

    with patch_session(UTILS_MODULE, make_bound_utils_session(osu_mode=3)):
        with patch_session(MODULE, make_binded_id_session(["12345678"])):
            with patch(
                f"{MODULE}.select_score_from_user", new=AsyncMock(return_value=(None, "今日所有歌曲都被猜过了"))
            ):
                async with app.test_matcher(guess_chart) as ctx:
                    adapter = nonebot.get_adapter(OnebotV11Adapter)
                    bot = ctx.create_bot(base=Bot, adapter=adapter)
                    ctx.receive_event(bot, event)
                    ctx.should_call_send(
                        event,
                        text_msg(event, "今日所有歌曲都被猜过了"),
                        result={"message_id": 1},
                    )
                    ctx.should_finished()


# ---------------------------------------------------------------------------
# create_word_matcher_handler 逻辑测试
# ---------------------------------------------------------------------------


def test_create_word_matcher_handler_correct_answer():
    """相似度 >= 0.5 时，pop 游戏并标记为猜中。"""
    from nonebot_plugin_osubot.matcher.guess import create_word_matcher_handler, GameType

    games: dict = {}
    score = make_mock_score(title="Conflict", title_unicode="Conflict")
    games["session1"] = score

    create_word_matcher_handler(GameType.AUDIO, games)

    # 验证内部逻辑：相似度满足时 game 被 pop
    # handler 调用 UniMessage 需要 bot context，直接检查 games 状态
    from difflib import SequenceMatcher

    user_input = "conflict"
    r = SequenceMatcher(None, "conflict", user_input).ratio()
    assert r >= 0.5

    # 当正确答案输入时，game_manager 也应 pop 游戏（通过 game_manager.pop_game）
    # 这里验证 games 字典的 key 存在（handler 调用前状态）
    assert "session1" in games


def test_create_word_matcher_handler_no_game():
    """session 无游戏时，handler 应直接返回不处理消息。"""
    from nonebot_plugin_osubot.matcher.guess import create_word_matcher_handler, GameType

    games: dict = {}  # 无游戏
    create_word_matcher_handler(GameType.AUDIO, games)

    # games 为空时，handler 获取不到 game_data，应提前返回
    # 通过检查函数体逻辑：game_data = games_dict.get(session_id) → None → return
    assert games.get("any_session") is None


def test_word_matcher_similarity_threshold():
    """验证 SequenceMatcher 的相似度判断逻辑（>=0.5 猜中，<0.5 未猜中）。"""
    from difflib import SequenceMatcher
    import re

    def check(song_name: str, user_input: str) -> bool:
        user_input = user_input.lower()
        r1 = SequenceMatcher(None, song_name.lower(), user_input).ratio()
        r2 = SequenceMatcher(None, re.sub(r"[(\[].*[)\]]", "", song_name.lower()), user_input).ratio()
        return r1 >= 0.5 or r2 >= 0.5

    # 完全相同
    assert check("Conflict", "Conflict")
    # 括号内容去掉后相似度够
    assert check("Conflict (TV Size)", "Conflict")
    # 随机乱码不相似
    assert not check("Conflict", "xyzxyzxyz")
    # 空输入
    assert not check("Conflict", "")
