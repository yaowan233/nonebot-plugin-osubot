import re
import random
import asyncio
from io import BytesIO
from pathlib import Path
from asyncio import TimerHandle
from difflib import SequenceMatcher

from PIL import Image
from graiax import silkcoder
from nonebot.log import logger
from nonebot.params import T_State
from nonebot.matcher import Matcher
from expiringdict import ExpiringDict
from nonebot import on_command, on_message
from graiax.silkcoder.utils import CoderError
from nonebot.internal.rule import Rule, Event
from nonebot_plugin_alconna import At, UniMsg, UniMessage
from nonebot_plugin_session import SessionId, SessionIdType

from ..utils import NGM
from ..info import get_bg
from .utils import split_msg
from ..schema import NewScore
from ..exceptions import NetworkError
from ..database.models import UserData
from ..mania import generate_preview_pic
from ..api import osu_api, safe_async_get
from ..file import map_path, download_tmp_osu
from ..draw.catch_preview import draw_cath_preview

games: dict[str, NewScore] = {}
pic_games: dict[str, NewScore] = {}
chart_games: dict[str, NewScore] = {}
timers: dict[str, TimerHandle] = {}
pic_timers: dict[str, TimerHandle] = {}
chart_timers: dict[str, TimerHandle] = {}
hint_dic = {"pic": False, "artist": False, "creator": False}
pic_hint_dic = {"artist": False, "creator": False, "audio": False}
chart_hint_dic = {"pic": False, "artist": False, "creator": False, "audio": False}
group_hint = {}
pic_group_hint = {}
chart_group_hint = {}
guess_audio = on_command("音频猜歌", priority=11, block=True)
guess_chart = on_command("谱面猜歌", priority=11, block=True)
guess_song_cache = ExpiringDict(1000, 60 * 60 * 24)
data_path = Path() / "data" / "osu"
pcm_path = data_path / "out.pcm"


async def get_random_beatmap_set(binded_id, group_id, ttl=10) -> (NewScore, str):
    if ttl == 0:
        return
    selected_user = random.choice(binded_id)
    if not selected_user:
        return
    user = await UserData.filter(user_id=selected_user).first()
    try:
        bp_info = await osu_api("bp", user.osu_id, NGM[str(user.osu_mode)])
    except NetworkError:
        return await get_random_beatmap_set(binded_id, group_id, ttl - 1)
    selected_score = random.choice([NewScore(**i) for i in bp_info])
    if selected_score.beatmapset.id not in guess_song_cache[group_id]:
        guess_song_cache[group_id].add(selected_score.beatmapset.id)
    else:
        return await get_random_beatmap_set(binded_id, group_id, ttl - 1)
    return selected_score, user.osu_name


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
    group_id = session_id
    binded_id = await UserData.filter(osu_mode=mode).values_list("user_id", flat=True)
    if not binded_id:
        await UniMessage.text("还没有人绑定该模式的osu账号呢，绑定了再来试试吧").finish(reply_to=True)
    if not guess_song_cache.get(group_id):
        guess_song_cache[group_id] = set()
    if msg.has(At):
        qq = msg.get(At)[0].target
        user_data = await UserData.get_or_none(user_id=qq)
        if not user_data:
            await UniMessage.text("该用户未绑定osu账号").finish(reply_to=True)
        try:
            bp_info = await osu_api("bp", user_data.osu_id, NGM[state["mode"]])
        except NetworkError as e:
            await UniMessage.text(f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}").finish(
                reply_to=True
            )
        bp_ls = [NewScore(**i) for i in bp_info]
        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[group_id]]
        if not filtered_bp_ls:
            await UniMessage.text(state["user"] + "的bp已经被你们猜过一遍了 －_－").finish(reply_to=True)
        selected_score = random.choice(filtered_bp_ls)
        guess_song_cache[group_id].add(selected_score.beatmapset.id)
        selected_user = user_data.osu_name
    elif state["user"]:
        try:
            bp_info = await osu_api("bp", state["user"], NGM[state["mode"]], is_name=True)
        except NetworkError as e:
            await UniMessage.text(f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}").finish(
                reply_to=True
            )
        bp_ls = [NewScore(**i) for i in bp_info]
        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[group_id]]
        if not filtered_bp_ls:
            await UniMessage.text(state["user"] + "的bp已经被你们猜过一遍了 －_－").finish(reply_to=True)
        selected_score = random.choice(filtered_bp_ls)
        guess_song_cache[group_id].add(selected_score.beatmapset.id)
        selected_user = state["user"]
    else:
        selected_score, selected_user = await get_random_beatmap_set(binded_id, group_id)
    if not selected_score:
        await UniMessage.text("好像没有可以猜的歌了，今天的猜歌就到此结束吧！").finish(reply_to=True)
    if games.get(group_id, None):
        await UniMessage.text("现在还有进行中的猜歌呢，请等待当前猜歌结束").finish(reply_to=True)
    games[group_id] = selected_score
    set_timeout(matcher, group_id)
    await UniMessage.text(
        f"开始音频猜歌游戏，猜猜下面音频的曲名吧，该曲抽选自{selected_user} {NGM[mode]} 模式的bp"
    ).send(reply_to=True)
    logger.info(f"本次猜歌名为: {selected_score.beatmapset.title}")
    path = map_path / f"{selected_score.beatmapset.id}"
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    audio_path = path / "audio.silk"
    if not audio_path.exists():
        audio = await safe_async_get(f"https://b.ppy.sh/preview/{selected_score.beatmapset.id}.mp3")
        if not audio:
            await UniMessage.text("音频下载失败了 qaq " + f"本次猜歌名为: {selected_score.beatmapset.title}").finish(
                reply_to=True
            )
        try:
            await silkcoder.async_encode(audio.read(), audio_path, ios_adaptive=True)
        except CoderError:
            await UniMessage.text("音频编码失败了 qaq " + f"本次猜歌名为: {selected_score.beatmapset.title}").finish(
                reply_to=True
            )
    with open(audio_path, "rb") as f:
        silk_byte = f.read()
    await UniMessage.audio(raw=silk_byte, name="audio.silk", mimetype="silk").finish()


async def stop_game(matcher: Matcher, cid: str):
    timers.pop(cid, None)
    if games.get(cid, None):
        game = games.pop(cid)
        if group_hint.get(cid, None):
            group_hint[cid] = None
        msg = f"猜歌超时，游戏结束，正确答案是{game.beatmapset.title_unicode}"
        if game.beatmapset.title_unicode != game.beatmapset.title:
            msg += f" [{game.beatmapset.title}]"
        await matcher.send(msg)


async def pic_stop_game(matcher: Matcher, cid: str):
    pic_timers.pop(cid, None)
    if pic_games.get(cid, None):
        game = pic_games.pop(cid)
        if pic_group_hint.get(cid, None):
            pic_group_hint[cid] = None
        msg = f"猜歌超时，游戏结束，正确答案是{game.beatmapset.title_unicode}"
        if game.beatmapset.title_unicode != game.beatmapset.title:
            msg += f" [{game.beatmapset.title}]"
        await matcher.send(msg)


async def chart_stop_game(matcher: Matcher, cid: str):
    chart_timers.pop(cid, None)
    if chart_games.get(cid, None):
        game = chart_games.pop(cid)
        if chart_group_hint.get(cid, None):
            chart_group_hint[cid] = None
        msg = f"猜歌超时，游戏结束，正确答案是{game.beatmapset.title_unicode}"
        if game.beatmapset.title_unicode != game.beatmapset.title:
            msg += f" [{game.beatmapset.title}]"
        await matcher.send(msg)


def set_timeout(matcher: Matcher, cid: str, timeout: float = 300):
    timer = timers.get(cid, None)
    if timer:
        timer.cancel()
    loop = asyncio.get_running_loop()
    timer = loop.call_later(timeout, lambda: asyncio.ensure_future(stop_game(matcher, cid)))
    timers[cid] = timer


def pic_set_timeout(matcher: Matcher, cid: str, timeout: float = 300):
    timer = pic_timers.get(cid, None)
    if timer:
        timer.cancel()
    loop = asyncio.get_running_loop()
    timer = loop.call_later(timeout, lambda: asyncio.ensure_future(pic_stop_game(matcher, cid)))
    pic_timers[cid] = timer


def chart_set_timeout(matcher: Matcher, cid: str, timeout: float = 300):
    timer = chart_timers.get(cid, None)
    if timer:
        timer.cancel()
    loop = asyncio.get_running_loop()
    timer = loop.call_later(timeout, lambda: asyncio.ensure_future(chart_stop_game(matcher, cid)))
    chart_timers[cid] = timer


def game_running(session_id: str = SessionId(SessionIdType.GROUP)) -> bool:
    return bool(games.get(session_id, None))


def pic_game_running(session_id: str = SessionId(SessionIdType.GROUP)) -> bool:
    return bool(pic_games.get(session_id, None))


def chart_game_running(session_id: str = SessionId(SessionIdType.GROUP)) -> bool:
    return bool(chart_games.get(session_id, None))


word_matcher = on_message(Rule(game_running), priority=12)
pic_word_matcher = on_message(Rule(pic_game_running), priority=12)
chart_word_matcher = on_message(Rule(chart_game_running), priority=12)


@word_matcher.handle()
async def _(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
    song_name = games[session_id].beatmapset.title
    song_name_unicode = games[session_id].beatmapset.title_unicode
    r1 = SequenceMatcher(None, song_name.lower(), event.get_plaintext().lower()).ratio()
    r2 = SequenceMatcher(None, song_name_unicode.lower(), event.get_plaintext().lower()).ratio()
    r3 = SequenceMatcher(
        None,
        re.sub(r"[(\[].*[)\]]", "", song_name.lower()),
        event.get_plaintext().lower(),
    ).ratio()
    r4 = SequenceMatcher(
        None,
        re.sub(r"[(\[].*[)\]]", "", song_name_unicode.lower()),
        event.get_plaintext().lower(),
    ).ratio()
    if r1 >= 0.5 or r2 >= 0.5 or r3 >= 0.5 or r4 >= 0.5:
        games.pop(session_id)
        if group_hint.get(session_id, None):
            group_hint[session_id] = None
        msg = f"恭喜猜出正确答案为{song_name_unicode}"
        await UniMessage.text(msg).send(reply_to=True)


@pic_word_matcher.handle()
async def _(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
    song_name = pic_games[session_id].beatmapset.title
    song_name_unicode = pic_games[session_id].beatmapset.title_unicode
    r1 = SequenceMatcher(None, song_name.lower(), event.get_plaintext().lower()).ratio()
    r2 = SequenceMatcher(None, song_name_unicode.lower(), event.get_plaintext().lower()).ratio()
    r3 = SequenceMatcher(
        None,
        re.sub(r"[(\[].*[)\]]", "", song_name.lower()),
        event.get_plaintext().lower(),
    ).ratio()
    r4 = SequenceMatcher(
        None,
        re.sub(r"[(\[].*[)\]]", "", song_name_unicode.lower()),
        event.get_plaintext().lower(),
    ).ratio()
    if r1 >= 0.5 or r2 >= 0.5 or r3 >= 0.5 or r4 >= 0.5:
        pic_games.pop(session_id)
        if pic_group_hint.get(session_id, None):
            pic_group_hint[session_id] = None
        msg = f"恭喜猜出正确答案为{song_name_unicode}"
        await UniMessage.text(msg).send(reply_to=True)


hint = on_command("音频提示", priority=11, block=True, rule=Rule(game_running))


@hint.handle()
async def _(session_id: str = SessionId(SessionIdType.GROUP)):
    score = games[session_id]
    if not group_hint.get(session_id, None):
        group_hint[session_id] = hint_dic.copy()
    if all(group_hint[session_id].values()):
        await UniMessage.text("已无更多提示，加油哦").finish(reply_to=True)
    true_keys = []
    for key, value in group_hint[session_id].items():
        if not value:
            true_keys.append(key)
    action = random.choice(true_keys)
    if action == "pic":
        group_hint[session_id]["pic"] = True
        await UniMessage.image(url=score.beatmapset.covers.cover).finish(reply_to=True)
    if action == "artist":
        group_hint[session_id]["artist"] = True
        msg = f"曲师为：{score.beatmapset.artist_unicode}"
        if score.beatmapset.artist_unicode != score.beatmapset.artist:
            msg += f" [{score.beatmapset.artist}]"
        await UniMessage.text(msg).finish(reply_to=True)
    if action == "creator":
        group_hint[session_id]["creator"] = True
        await UniMessage.text(f"谱师为：{score.beatmapset.creator}").finish(reply_to=True)


pic_hint = on_command("图片提示", priority=11, block=True, rule=Rule(pic_game_running))


@pic_hint.handle()
async def _(session_id: str = SessionId(SessionIdType.GROUP)):
    score = pic_games[session_id]
    if not pic_group_hint.get(session_id, None):
        pic_group_hint[session_id] = pic_hint_dic.copy()
    if all(pic_group_hint[session_id].values()):
        await pic_hint.finish("已无更多提示，加油哦")
    true_keys = []
    for key, value in pic_group_hint[session_id].items():
        if not value:
            true_keys.append(key)
    action = random.choice(true_keys)
    if action == "audio":
        pic_group_hint[session_id]["audio"] = True
        path = map_path / f"{score.beatmapset.id}"
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        audio_path = map_path / f"{score.beatmapset.id}" / "audio.silk"
        if not audio_path.exists():
            audio = await safe_async_get(f"https://b.ppy.sh/preview/{score.beatmapset.id}.mp3")
            if not audio:
                await UniMessage.text("音频下载失败了 qaq ").finish(reply_to=True)
            try:
                await silkcoder.async_encode(audio.read(), audio_path, ios_adaptive=True)
            except CoderError:
                await UniMessage.text("音频编码失败了 qaq").finish(reply_to=True)
        with open(audio_path, "rb") as f:
            silk_byte = f.read()
        await UniMessage.audio(raw=silk_byte, name="audio.silk", mimetype="silk").finish()
    if action == "artist":
        pic_group_hint[session_id]["artist"] = True
        msg = f"曲师为：{score.beatmapset.artist_unicode}"
        if score.beatmapset.artist_unicode != score.beatmapset.artist:
            msg += f" [{score.beatmapset.artist}]"
        await pic_hint.finish(msg)
    if action == "creator":
        pic_group_hint[session_id]["creator"] = True
        await pic_hint.finish(f"谱师为：{score.beatmapset.creator}")


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
    if not guess_song_cache.get(session_id):
        guess_song_cache[session_id] = set()
    if msg.has(At):
        qq = msg.get(At)[0].target
        user_data = await UserData.get_or_none(user_id=int(qq))
        if not user_data:
            await UniMessage.text("该用户未绑定osu账号").finish(reply_to=True)
        try:
            bp_info = await osu_api("bp", user_data.osu_id, NGM[state["mode"]])
        except NetworkError as e:
            await UniMessage.text(f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}").finish(
                reply_to=True
            )
        bp_ls = [NewScore(**i) for i in bp_info]
        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[session_id]]
        if not filtered_bp_ls:
            await UniMessage.text(state["user"] + "的bp已经被你们猜过一遍了 －_－").finish(reply_to=True)
        selected_score = random.choice(filtered_bp_ls)
        guess_song_cache[session_id].add(selected_score.beatmapset.id)
        selected_user = user_data.osu_name
    elif state["user"]:
        try:
            bp_info = await osu_api("bp", state["user"], NGM[state["mode"]], is_name=True)
        except NetworkError as e:
            await UniMessage.text(f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}").finish(
                reply_to=True
            )
        bp_ls = [NewScore(**i) for i in bp_info]
        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[session_id]]
        if not filtered_bp_ls:
            await UniMessage.text(state["user"] + "的bp已经被你们猜过一遍了 －_－").finish(reply_to=True)
        selected_score = random.choice(filtered_bp_ls)
        guess_song_cache[session_id].add(selected_score.beatmapset.id)
        selected_user = state["user"]
    else:
        selected_score, selected_user = await get_random_beatmap_set(binded_id, session_id)
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
    if mode == "0" or mode == "1":
        await UniMessage.text("该模式暂不支持猜歌").finish(reply_to=True)
    binded_id = await UserData.filter(osu_mode=mode).values_list("user_id", flat=True)
    if not binded_id:
        await guess_pic.finish("还没有人绑定该模式的osu账号呢，绑定了再来试试吧")
    if not guess_song_cache.get(session_id):
        guess_song_cache[session_id] = set()
    if msg.has(At):
        qq = msg.get(At)[0].target
        user_data = await UserData.get_or_none(user_id=int(qq))
        if not user_data:
            await UniMessage.text("该用户未绑定osu账号").finish(reply_to=True)
        try:
            bp_info = await osu_api("bp", user_data.osu_id, NGM[state["mode"]])
        except NetworkError as e:
            await UniMessage.text(f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}").finish(
                reply_to=True
            )
        bp_ls = [NewScore(**i) for i in bp_info]
        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[session_id]]
        if not filtered_bp_ls:
            await UniMessage.text(state["user"] + "的bp已经被你们猜过一遍了 －_－").finish(reply_to=True)
        selected_score = random.choice(filtered_bp_ls)
        selected_user = user_data.osu_name
        guess_song_cache[session_id].add(selected_score.beatmapset.id)
    elif state["user"]:
        try:
            bp_info = await osu_api("bp", state["user"], NGM[state["mode"]], is_name=True)
        except NetworkError as e:
            await UniMessage.text(f"在查找用户：{state['username']} {NGM[state['mode']]}模式bp时 {str(e)}").finish(
                reply_to=True
            )
        bp_ls = [NewScore(**i) for i in bp_info]
        filtered_bp_ls = [i for i in bp_ls if i.beatmapset.id not in guess_song_cache[session_id]]
        if not filtered_bp_ls:
            await UniMessage.text(state["user"] + "的bp已经被你们猜过一遍了 －_－").finish(reply_to=True)
        selected_score = random.choice(filtered_bp_ls)
        selected_user = state["user"]
        guess_song_cache[session_id].add(selected_score.beatmapset.id)
    else:
        selected_score, selected_user = await get_random_beatmap_set(binded_id, session_id)
    if not selected_score:
        await guess_pic.finish("好像没有可以猜的歌了，今天的猜歌就到此结束吧！")
    if chart_games.get(session_id, None):
        await guess_pic.finish("现在还有进行中的猜歌呢，请等待当前猜歌结束")
    chart_games[session_id] = selected_score
    chart_set_timeout(matcher, session_id)
    if mode == "3":
        osu = await download_tmp_osu(selected_score.beatmap.id)
        byt = await generate_preview_pic(osu)
        await (
            UniMessage.text(f"开始谱面猜歌游戏，猜猜下面谱面的曲名吧，该曲抽选自 {selected_user} 的bp")
            + UniMessage.image(raw=byt)
        ).finish()
    else:
        mods = [i.acronym for i in selected_score.mods]
        pic = await draw_cath_preview(selected_score.beatmap.id, selected_score.beatmapset.id, mods)
        await (
            UniMessage.text(f"开始谱面猜歌游戏，猜猜下面谱面的曲名吧，该曲抽选自 {selected_user} 的bp")
            + UniMessage.image(raw=pic)
        ).finish()


@chart_word_matcher.handle()
async def _(event: Event, session_id: str = SessionId(SessionIdType.GROUP)):
    song_name = chart_games[session_id].beatmapset.title
    song_name_unicode = chart_games[session_id].beatmapset.title_unicode
    r1 = SequenceMatcher(None, song_name.lower(), event.get_plaintext().lower()).ratio()
    r2 = SequenceMatcher(None, song_name_unicode.lower(), event.get_plaintext().lower()).ratio()
    r3 = SequenceMatcher(
        None,
        re.sub(r"[(\[].*[)\]]", "", song_name.lower()),
        event.get_plaintext().lower(),
    ).ratio()
    if r1 >= 0.5 or r2 >= 0.5 or r3 >= 0.5:
        chart_games.pop(session_id)
        if chart_group_hint.get(session_id, None):
            chart_group_hint[session_id] = None
        msg = f"恭喜猜出正确答案为{song_name_unicode}"
        await UniMessage.text(msg).send(reply_to=True)


chart_hint = on_command("谱面提示", priority=11, block=True, rule=Rule(chart_game_running))


@chart_hint.handle()
async def _(session_id: str = SessionId(SessionIdType.GROUP)):
    score = chart_games[session_id]
    if not chart_group_hint.get(session_id, None):
        chart_group_hint[session_id] = chart_hint_dic.copy()
    if all(chart_group_hint[session_id].values()):
        await chart_hint.finish("已无更多提示，加油哦")
    true_keys = []
    for key, value in chart_group_hint[session_id].items():
        if not value:
            true_keys.append(key)
    action = random.choice(true_keys)
    if action == "audio":
        chart_group_hint[session_id]["audio"] = True
        path = map_path / f"{score.beatmapset.id}"
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        audio_path = map_path / f"{score.beatmapset.id}" / "audio.silk"
        if not audio_path.exists():
            audio = await safe_async_get(f"https://b.ppy.sh/preview/{score.beatmapset.id}.mp3")
            if not audio:
                await UniMessage.text("音频下载失败了 qaq ").finish(reply_to=True)
            try:
                await silkcoder.async_encode(audio.read(), audio_path, ios_adaptive=True)
            except CoderError:
                await UniMessage.text("音频编码失败了 qaq").finish(reply_to=True)
        with open(audio_path, "rb") as f:
            silk_byte = f.read()
        await UniMessage.audio(raw=silk_byte, name="audio.silk", mimetype="silk").finish()
    if action == "artist":
        chart_group_hint[session_id]["artist"] = True
        msg = f"曲师为：{score.beatmapset.artist_unicode}"
        if score.beatmapset.artist_unicode != score.beatmapset.artist:
            msg += f" [{score.beatmapset.artist}]"
        await chart_hint.finish(msg)
    if action == "creator":
        chart_group_hint[session_id]["creator"] = True
        await chart_hint.finish(f"谱师为：{score.beatmapset.creator}")
    if action == "pic":
        chart_group_hint[session_id]["pic"] = True
        await UniMessage.image(url=score.beatmapset.covers.cover).finish(reply_to=True)
