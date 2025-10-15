import re
import random
import asyncio
from io import BytesIO
from pathlib import Path
from asyncio import TimerHandle
from difflib import SequenceMatcher

from PIL import Image
from nonebot.log import logger
from nonebot.params import T_State
from nonebot.matcher import Matcher
from expiringdict import ExpiringDict
from nonebot import on_command, on_message
from nonebot.internal.rule import Rule, Event
from nonebot_plugin_alconna import At, UniMsg, UniMessage
from nonebot_plugin_session import SessionId, SessionIdType

from ..draw.taiko_preview import parse_map, map_to_image
from ..schema.score import UnifiedScore
from ..utils import NGM
from ..info import get_bg
from .utils import split_msg
from ..schema import NewScore
from ..exceptions import NetworkError
from ..database.models import UserData
from ..mania import generate_preview_pic
from ..api import safe_async_get, get_user_scores
from ..file import map_path, download_osu
from ..draw.catch_preview import draw_cath_preview


class GameType:
    AUDIO = "audio"
    PIC = "pic"
    CHART = "chart"


class GameManager:
    def __init__(self):
        self.games: dict[str, dict[str, NewScore]] = {GameType.AUDIO: {}, GameType.PIC: {}, GameType.CHART: {}}
        self.timers: dict[str, dict[str, TimerHandle]] = {GameType.AUDIO: {}, GameType.PIC: {}, GameType.CHART: {}}
        self.hint_templates = {
            GameType.AUDIO: {"pic": False, "artist": False, "creator": False},
            GameType.PIC: {"artist": False, "creator": False, "audio": False},
            GameType.CHART: {"pic": False, "artist": False, "creator": False, "audio": False},
        }
        self.group_hints: dict[str, dict[str, dict[str, bool]]] = {
            GameType.AUDIO: {},
            GameType.PIC: {},
            GameType.CHART: {},
        }

    def get_game(self, game_type: str, session_id: str):
        return self.games[game_type].get(session_id)

    def set_game(self, game_type: str, session_id: str, score: NewScore):
        self.games[game_type][session_id] = score

    def pop_game(self, game_type: str, session_id: str):
        return self.games[game_type].pop(session_id, None)

    def get_timer(self, game_type: str, session_id: str):
        return self.timers[game_type].get(session_id)

    def set_timer(self, game_type: str, session_id: str, timer: TimerHandle):
        self.timers[game_type][session_id] = timer

    def pop_timer(self, game_type: str, session_id: str):
        return self.timers[game_type].pop(session_id, None)

    def get_hint(self, game_type: str, session_id: str):
        return self.group_hints[game_type].get(session_id)

    def init_hint(self, game_type: str, session_id: str):
        self.group_hints[game_type][session_id] = self.hint_templates[game_type].copy()

    def reset_hint(self, game_type: str, session_id: str):
        self.group_hints[game_type][session_id] = None

    def is_game_running(self, game_type: str, session_id: str) -> bool:
        return bool(self.games[game_type].get(session_id))


game_manager = GameManager()

# Keep old references for backward compatibility during transition
games = game_manager.games[GameType.AUDIO]
pic_games = game_manager.games[GameType.PIC]
chart_games = game_manager.games[GameType.CHART]
timers = game_manager.timers[GameType.AUDIO]
pic_timers = game_manager.timers[GameType.PIC]
chart_timers = game_manager.timers[GameType.CHART]
hint_dic = game_manager.hint_templates[GameType.AUDIO]
pic_hint_dic = game_manager.hint_templates[GameType.PIC]
chart_hint_dic = game_manager.hint_templates[GameType.CHART]
group_hint = game_manager.group_hints[GameType.AUDIO]
pic_group_hint = game_manager.group_hints[GameType.PIC]
chart_group_hint = game_manager.group_hints[GameType.CHART]
guess_audio = on_command("音频猜歌", priority=11, block=True)
guess_chart = on_command("谱面猜歌", priority=11, block=True)
guess_song_cache = ExpiringDict(1000, 60 * 60 * 24)
data_path = Path() / "data" / "osu"
pcm_path = data_path / "out.pcm"


async def get_random_beatmap_set(binded_id, group_id) -> (UnifiedScore, str):
    # 获取已猜过的歌曲集合
    guessed_songs = guess_song_cache[group_id]
    available_scores = []
    for user_id in binded_id:
        try:
            user = await UserData.filter(user_id=user_id).first()
            if not user:
                continue
            bp_info = await get_user_scores(user.osu_id, NGM[str(user.osu_mode)], "best")
            # 过滤掉已猜过的歌曲
            unguessed_scores = [(score, user.osu_name) for score in bp_info if score.beatmapset.id not in guessed_songs]
            available_scores.extend(unguessed_scores)
        except NetworkError:
            continue  # 跳过网络错误的用户，继续尝试其他用户
    if not available_scores:
        return None, None  # 所有歌曲都被猜过了
    # 随机选择一个未猜过的成绩
    selected_score, osu_name = random.choice(available_scores)
    guess_song_cache[group_id].add(selected_score.beatmapset.id)
    return selected_score, osu_name


async def select_score_from_user(state: T_State, msg: UniMsg, session_id: str):
    """
    Common logic for selecting a score from a specific user or randomly.
    Returns (selected_score, selected_user) or (None, error_msg).
    """
    mode = state.get("mode", str(random.randint(0, 3)))
    binded_id = await UserData.filter(osu_mode=mode).values_list("user_id", flat=True)

    if not guess_song_cache.get(session_id):
        guess_song_cache[session_id] = set()

    # Handle @mention
    if msg.has(At):
        qq = msg.get(At)[0].target
        user_data = await UserData.get_or_none(user_id=int(qq))
        if not user_data:
            return None, "该用户未绑定osu账号"
        try:
            bp_ls = await get_user_scores(user_data.osu_id, NGM[state["mode"]], "best")
        except NetworkError as e:
            return None, f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}"

        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[session_id]]
        if not filtered_bp_ls:
            return None, f"{state['username']}的bp已经被你们猜过一遍了 －_－"

        selected_score = random.choice(filtered_bp_ls)
        guess_song_cache[session_id].add(selected_score.beatmapset.id)
        return selected_score, user_data.osu_name

    # Handle specific user from state
    elif state.get("user"):
        try:
            bp_ls = await get_user_scores(state["user"], NGM[state["mode"]], "best")
        except NetworkError as e:
            return None, f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}"

        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[session_id]]
        if not filtered_bp_ls:
            return None, f"{state['username']}的bp已经被你们猜过一遍了 －_－"

        selected_score = random.choice(filtered_bp_ls)
        guess_song_cache[session_id].add(selected_score.beatmapset.id)
        return selected_score, state["username"]

    # Random selection
    else:
        return await get_random_beatmap_set(binded_id, session_id)


@guess_audio.handle(parameterless=[split_msg()])
async def _(
    state: T_State,
    matcher: Matcher,
    msg: UniMsg,
    session_id: str = SessionId(SessionIdType.GROUP),
):
    if "error" in state:
        mode = str(random.randint(0, 3))
        await UniMessage.text("由于未绑定OSU账号，本次随机挑选模式进行猜歌\n" + state["error"]).send(reply_to=True)
    else:
        mode = state["mode"]

    binded_id = await UserData.filter(osu_mode=mode).values_list("user_id", flat=True)
    if not binded_id:
        await UniMessage.text("还没有人绑定该模式的osu账号呢，绑定了再来试试吧").finish(reply_to=True)

    result = await select_score_from_user(state, msg, session_id)
    if result[0] is None:
        await UniMessage.text(result[1]).finish(reply_to=True)
    selected_score, selected_user = result

    if not selected_score:
        await UniMessage.text("好像没有可以猜的歌了，今天的猜歌就到此结束吧！").finish(reply_to=True)

    if games.get(session_id, None):
        await UniMessage.text("现在还有进行中的猜歌呢，请等待当前猜歌结束").finish(reply_to=True)

    games[session_id] = selected_score
    set_timeout(matcher, session_id)
    await UniMessage.text(
        f"开始音频猜歌游戏，猜猜下面音频的曲名吧，该曲抽选自{selected_user} {NGM[mode]} 模式的bp"
    ).send(reply_to=True)
    logger.info(f"本次猜歌名为: {selected_score.beatmapset.title}")
    path = map_path / f"{selected_score.beatmapset.id}"
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    audio = await safe_async_get(f"https://b.ppy.sh/preview/{selected_score.beatmapset.id}.mp3")
    if not audio:
        await UniMessage.text("音频下载失败了 qaq ").finish(reply_to=True)
    await UniMessage.audio(raw=audio.read()).finish()


async def stop_game_generic(matcher: Matcher, game_type: str, cid: str):
    game_manager.pop_timer(game_type, cid)
    game = game_manager.pop_game(game_type, cid)
    if game:
        game_manager.reset_hint(game_type, cid)
        msg = f"猜歌超时，游戏结束，正确答案是{game.beatmapset.title_unicode}"
        if game.beatmapset.title_unicode != game.beatmapset.title:
            msg += f" [{game.beatmapset.title}]"
        await matcher.send(msg)


async def stop_game(matcher: Matcher, cid: str):
    await stop_game_generic(matcher, GameType.AUDIO, cid)


async def pic_stop_game(matcher: Matcher, cid: str):
    await stop_game_generic(matcher, GameType.PIC, cid)


async def chart_stop_game(matcher: Matcher, cid: str):
    await stop_game_generic(matcher, GameType.CHART, cid)


def set_timeout_generic(matcher: Matcher, game_type: str, stop_func, cid: str, timeout: float = 300):
    timer = game_manager.get_timer(game_type, cid)
    if timer:
        timer.cancel()
    loop = asyncio.get_running_loop()
    timer = loop.call_later(timeout, lambda: asyncio.ensure_future(stop_func(matcher, cid)))
    game_manager.set_timer(game_type, cid, timer)


def set_timeout(matcher: Matcher, cid: str, timeout: float = 300):
    set_timeout_generic(matcher, GameType.AUDIO, stop_game, cid, timeout)


def pic_set_timeout(matcher: Matcher, cid: str, timeout: float = 300):
    set_timeout_generic(matcher, GameType.PIC, pic_stop_game, cid, timeout)


def chart_set_timeout(matcher: Matcher, cid: str, timeout: float = 300):
    set_timeout_generic(matcher, GameType.CHART, chart_stop_game, cid, timeout)


def game_running(session_id: str = SessionId(SessionIdType.GROUP)) -> bool:
    return bool(games.get(session_id, None))


def pic_game_running(session_id: str = SessionId(SessionIdType.GROUP)) -> bool:
    return bool(pic_games.get(session_id, None))


def chart_game_running(session_id: str = SessionId(SessionIdType.GROUP)) -> bool:
    return bool(chart_games.get(session_id, None))


def create_word_matcher_handler(game_type: str, games_dict: dict):
    """Factory function to create word matcher handlers for different game types."""

    async def handler(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
        song_name = games_dict[session_id].beatmapset.title
        song_name_unicode = games_dict[session_id].beatmapset.title_unicode
        user_input = event.get_plaintext().lower()

        # Calculate similarity ratios
        r1 = SequenceMatcher(None, song_name.lower(), user_input).ratio()
        r2 = SequenceMatcher(None, song_name_unicode.lower(), user_input).ratio()
        r3 = SequenceMatcher(None, re.sub(r"[(\[].*[)\]]", "", song_name.lower()), user_input).ratio()
        r4 = SequenceMatcher(None, re.sub(r"[(\[].*[)\]]", "", song_name_unicode.lower()), user_input).ratio()

        if r1 >= 0.5 or r2 >= 0.5 or r3 >= 0.5 or r4 >= 0.5:
            game_manager.pop_game(game_type, session_id)
            game_manager.reset_hint(game_type, session_id)
            msg = f"恭喜猜出正确答案为{song_name_unicode}"
            await UniMessage.text(msg).send(reply_to=True)

    return handler


word_matcher = on_message(Rule(game_running), priority=12)
pic_word_matcher = on_message(Rule(pic_game_running), priority=12)
chart_word_matcher = on_message(Rule(chart_game_running), priority=12)


@word_matcher.handle()
async def _(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
    await create_word_matcher_handler(GameType.AUDIO, games)(event, session_id)


@pic_word_matcher.handle()
async def _(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
    await create_word_matcher_handler(GameType.PIC, pic_games)(event, session_id)


@chart_word_matcher.handle()
async def _(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
    await create_word_matcher_handler(GameType.CHART, chart_games)(event, session_id)


async def handle_hint_generic(game_type: str, games_dict: dict, session_id: str, matcher):
    """Generic hint handler for all game types."""
    score = games_dict[session_id]

    if not game_manager.get_hint(game_type, session_id):
        game_manager.init_hint(game_type, session_id)

    hints = game_manager.get_hint(game_type, session_id)
    if all(hints.values()):
        await UniMessage.text("已无更多提示，加油哦").finish(reply_to=True)

    # Get available hint types
    available_hints = [key for key, value in hints.items() if not value]
    action = random.choice(available_hints)

    # Mark hint as used
    hints[action] = True

    # Provide hint based on action
    if action == "pic":
        await UniMessage.image(url=score.beatmapset.covers.cover).finish(reply_to=True)
    elif action == "artist":
        msg = f"曲师为：{score.beatmapset.artist_unicode}"
        if score.beatmapset.artist_unicode != score.beatmapset.artist:
            msg += f" [{score.beatmapset.artist}]"
        await matcher.finish(msg)
    elif action == "creator":
        await matcher.finish(f"谱师为：{score.beatmapset.creator}")
    elif action == "audio":
        path = map_path / f"{score.beatmapset.id}"
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        audio = await safe_async_get(f"https://b.ppy.sh/preview/{score.beatmapset.id}.mp3")
        if not audio:
            await UniMessage.text("音频下载失败了 qaq ").finish(reply_to=True)
        await UniMessage.audio(raw=audio.read()).finish()


hint = on_command("音频提示", priority=11, block=True, rule=Rule(game_running))


@hint.handle()
async def _(session_id: str = SessionId(SessionIdType.GROUP)):
    await handle_hint_generic(GameType.AUDIO, games, session_id, hint)


pic_hint = on_command("图片提示", priority=11, block=True, rule=Rule(pic_game_running))


@pic_hint.handle()
async def _(session_id: str = SessionId(SessionIdType.GROUP)):
    await handle_hint_generic(GameType.PIC, pic_games, session_id, pic_hint)


chart_hint = on_command("谱面提示", priority=11, block=True, rule=Rule(chart_game_running))


@chart_hint.handle()
async def _(session_id: str = SessionId(SessionIdType.GROUP)):
    await handle_hint_generic(GameType.CHART, chart_games, session_id, chart_hint)


guess_pic = on_command("图片猜歌", priority=11, block=True)


@guess_pic.handle(parameterless=[split_msg()])
async def _(
    state: T_State,
    matcher: Matcher,
    msg: UniMsg,
    session_id: str = SessionId(SessionIdType.GROUP),
):
    if "error" in state:
        mode = str(random.randint(0, 3))
        await UniMessage.text("由于未绑定OSU账号，本次随机选择模式进行猜歌\n" + state["error"]).send(reply_to=True)
    else:
        mode = state["mode"]

    binded_id = await UserData.filter(osu_mode=mode).values_list("user_id", flat=True)
    if not binded_id:
        await guess_pic.finish("还没有人绑定该模式的osu账号呢，绑定了再来试试吧")

    result = await select_score_from_user(state, msg, session_id)
    if result[0] is None:
        await UniMessage.text(result[1]).finish(reply_to=True)
    selected_score, selected_user = result

    if not selected_score:
        await guess_pic.finish("好像没有可以猜的歌了，今天的猜歌就到此结束吧！")

    if pic_games.get(session_id, None):
        await guess_pic.finish("现在还有进行中的猜歌呢，请等待当前猜歌结束")

    pic_games[session_id] = selected_score
    pic_set_timeout(matcher, session_id)
    try:
        byt = await get_bg(selected_score.beatmap.id)
    except NetworkError:
        await guess_pic.finish(f"本次猜歌名为: {selected_score.beatmapset.title_unicode}" + str(NetworkError))
    img = Image.open(byt)
    width, height = img.size
    crop_width = int(width * 0.3)
    crop_height = int(height * 0.3)
    left = random.randint(0, width - crop_width)
    top = random.randint(0, height - crop_height)
    right = left + crop_width
    bottom = top + crop_height
    cropped_image = img.crop((left, top, right, bottom))
    byt = BytesIO()
    cropped_image.save(byt, "png")
    logger.info(f"本次猜歌名为: {selected_score.beatmapset.title_unicode}")
    await (
        UniMessage.text(f"开始图片猜歌游戏，猜猜下面图片的曲名吧，该曲抽选自{selected_user} {NGM[mode]} 模式的bp")
        + UniMessage.image(raw=byt)
    ).finish()


@guess_chart.handle(parameterless=[split_msg()])
async def _(
    state: T_State,
    matcher: Matcher,
    msg: UniMsg,
    session_id: str = SessionId(SessionIdType.GROUP),
):
    if "error" in state:
        mode = str(random.randint(0, 3))
        await UniMessage.text("由于未绑定OSU账号，本次随机选择模式进行猜歌\n" + state["error"]).send(reply_to=True)
    else:
        mode = state["mode"]

    if mode == "0":
        await UniMessage.text("该模式暂不支持猜歌").finish(reply_to=True)

    binded_id = await UserData.filter(osu_mode=mode).values_list("user_id", flat=True)
    if not binded_id:
        await guess_pic.finish("还没有人绑定该模式的osu账号呢，绑定了再来试试吧")

    result = await select_score_from_user(state, msg, session_id)
    if result[0] is None:
        await UniMessage.text(result[1]).finish(reply_to=True)
    selected_score, selected_user = result

    if not selected_score:
        await guess_pic.finish("好像没有可以猜的歌了，今天的猜歌就到此结束吧！")

    if chart_games.get(session_id, None):
        await guess_pic.finish("现在还有进行中的猜歌呢，请等待当前猜歌结束")

    chart_games[session_id] = selected_score
    chart_set_timeout(matcher, session_id)
    if mode == "3":
        osu = await download_osu(selected_score.beatmapset.id, selected_score.beatmap.id)
        pic = await generate_preview_pic(osu)
    elif mode == "1":
        osu = await download_osu(selected_score.beatmapset.id, selected_score.beatmap.id)
        beatmap = parse_map(osu)
        pic = map_to_image(beatmap)
    else:
        mods = [i.acronym for i in selected_score.mods]
        pic = await draw_cath_preview(selected_score.beatmap.id, selected_score.beatmapset.id, mods)
    await (
        UniMessage.text(f"开始谱面猜歌游戏，猜猜下面谱面的曲名吧，该曲抽选自 {selected_user} 的bp")
        + UniMessage.image(raw=pic)
    ).finish()


@chart_word_matcher.handle()
async def _(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
    await create_word_matcher_handler(GameType.CHART, chart_games)(event, session_id)


chart_hint = on_command("谱面提示", priority=11, block=True, rule=Rule(chart_game_running))


@chart_hint.handle()
async def _(session_id: str = SessionId(SessionIdType.GROUP)):
    await handle_hint_generic(GameType.CHART, chart_games, session_id, chart_hint)
