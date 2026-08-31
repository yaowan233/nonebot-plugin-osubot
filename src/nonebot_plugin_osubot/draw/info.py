import asyncio
import base64
from typing import Union
from datetime import date, datetime, timedelta

from PIL import UnidentifiedImageError

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from .utils import info_calc
from .info_svg import render_info_svg
from .score import _player_avatar_data_uri, _team_icon_data
from .svg_render import file_data_uri, thumbnail_data_uri
from ..mods import get_speed_change_labels
from ..pp import cal_stars
from ..utils import FGM, GMN
from ..file import badge_cache_file, user_cache_path, ensure_osu_file, get_pfm_img, make_badge_cache_file, map_path
from ..exceptions import NetworkError
from ..database.models import InfoData
from ..schema.draw_info import DrawUser, Badge, DrawBestPlay
from ..schema.user import UnifiedUser
from ..api import get_user_info_data, get_user_scores


_STAR_RATING_MODS = frozenset({"DT", "NC", "HT", "HR", "EZ", "DC", "DA"})


def _has_star_rating_mod(score) -> bool:
    return any(mod.acronym.upper() in _STAR_RATING_MODS for mod in score.mods)


async def draw_info(
    uid: Union[int, str],
    mode: str,
    day: int,
    source: str,
    *,
    return_info: bool = False,
) -> bytes | tuple[bytes, UnifiedUser]:
    score_task = None
    if isinstance(uid, int) or str(uid).isdigit():
        score_task = asyncio.create_task(get_user_scores(uid, mode, "best", source=source, limit=10))
    try:
        info = await get_user_info_data(uid, mode, source)
    except BaseException:
        if score_task and not score_task.done():
            score_task.cancel()
        if score_task:
            await asyncio.gather(score_task, return_exceptions=True)
        raise
    try:
        scores = (
            await score_task
            if score_task is not None
            else await get_user_scores(info.id, mode, "best", source=source, limit=10)
        )[:10]
    except Exception:
        scores = []
    statistics = info.statistics
    if statistics.play_count == 0:
        raise NetworkError(f"此玩家尚未游玩过{GMN[mode]}模式")

    visible_badges = (info.badges or [])[:8]
    mapped_scores = [score for score in scores if score.beatmap]
    cover_paths = [map_path / str(score.beatmap.set_id) / "cover.jpg" for score in mapped_scores]
    cover_downloads = {}
    for score, cover_path in zip(mapped_scores, cover_paths):
        if not cover_path.exists():
            cover_downloads.setdefault(
                cover_path,
                (
                    score.beatmapset.covers.list
                    if score.beatmapset and score.beatmapset.covers
                    else f"https://assets.ppy.sh/beatmaps/{score.beatmap.set_id}/covers/list@2x.jpg"
                ),
            )

    async def prepare_resources():
        results = await asyncio.gather(
            asyncio.wait_for(_player_avatar_data_uri(info, source), timeout=3),
            asyncio.wait_for(_team_icon_data(info), timeout=3),
            *(asyncio.wait_for(make_badge_cache_file(badge), timeout=3.5) for badge in visible_badges),
            *(
                asyncio.wait_for(
                    ensure_osu_file(score.beatmap.set_id, score.beatmap.id, score.beatmap.checksum),
                    timeout=5,
                )
                for score in mapped_scores
                if _has_star_rating_mod(score)
            ),
            *(asyncio.wait_for(get_pfm_img(url, cover_path), timeout=5) for cover_path, url in cover_downloads.items()),
            return_exceptions=True,
        )
        return results[0], results[1]

    resources_task = asyncio.create_task(prepare_resources())
    # 对比
    user = None
    if source == "osu":
        try:
            async with get_session() as session:
                user = await session.scalar(
                    select(InfoData)
                    .where(InfoData.osu_id == info.id, InfoData.osu_mode == FGM[mode])
                    .order_by(InfoData.date.desc())
                )
                if user:
                    today_date = date.today()
                    # 补全今天记录的 c_rank（批量更新接口不返回 country_rank）
                    today_record = await session.scalar(
                        select(InfoData).where(
                            InfoData.osu_id == info.id,
                            InfoData.osu_mode == FGM[mode],
                            InfoData.date == today_date,
                        )
                    )
                    if today_record and today_record.c_rank is None and statistics.country_rank is not None:
                        today_record.c_rank = statistics.country_rank
                        await session.commit()
                    query_date = today_date - timedelta(days=day)
                    user = await session.scalar(
                        select(InfoData)
                        .where(
                            InfoData.osu_id == info.id,
                            InfoData.osu_mode == FGM[mode],
                            InfoData.date >= query_date,
                        )
                        .order_by(InfoData.date)
                    )
        except BaseException:
            resources_task.cancel()
            await asyncio.gather(resources_task, return_exceptions=True)
            raise
    avatar_data, team_data = await resources_task
    if user:
        n_crank = user.c_rank
        n_grank = user.g_rank
        n_pp = user.pp
        n_acc = user.acc
        n_pc = user.pc
        n_count = user.count
        n_ranked_score = user.ranked_score
        n_total_score = user.total_score
        n_xh = user.count_xh
        n_x = user.count_x
        n_sh = user.count_sh
        n_s = user.count_s
        n_a = user.count_a
        n_play_time = user.play_time
        n_badge_count = user.badge_count
    else:
        gc = statistics.grade_counts
        n_crank = statistics.country_rank
        n_grank = statistics.global_rank
        n_pp = statistics.pp
        n_acc = statistics.hit_accuracy
        n_pc = statistics.play_count
        n_count = statistics.total_hits
        n_ranked_score = statistics.ranked_score
        n_total_score = statistics.total_score
        n_xh = gc.ssh
        n_x = gc.ss
        n_sh = gc.sh
        n_s = gc.s
        n_a = gc.a
        n_play_time = statistics.play_time
        n_badge_count = len(info.badges) if info.badges else 0
    # 获取背景
    bg_path = user_cache_path / str(info.id) / "info.png"
    if bg_path.exists():
        try:
            with open(bg_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

            # 格式化为 CSS 接受的 data URI 格式
            bg = f"data:image/png;base64,{encoded_string}"
        except UnidentifiedImageError:
            bg_path.unlink()
            raise NetworkError("自定义背景图片读取错误，请重新上传！")
    else:
        # 无自定义背景时留空：随机图在深色面板下几乎不可见，且下载接口异常会卡住出图
        bg = ""
    if day != 0 and user:
        day_delta = date.today() - user.date
        time = day_delta.days
        footer = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        footer += f" | 数据对比于 {time} 天前"
    else:
        footer = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    op, value = info_calc(statistics.pp, n_pp, pp=True)
    pp_change = f"{op}{value:,.2f}" if value != 0 else None
    op, value = info_calc(statistics.global_rank, n_grank, rank=True)
    rank_change = f"{op}{value:,}" if value != 0 else None
    op, value = info_calc(statistics.country_rank, n_crank, rank=True)
    country_rank_change = f"({op}{value:,})" if value != 0 else None
    # acc
    op, value = info_calc(statistics.hit_accuracy, n_acc)
    acc_change = f"({op}{value:.2f}%)" if value != 0 else None

    def _fmt_change(cur, prev, fmt=",", suffix=""):
        if prev is None:
            return None
        op, value = info_calc(cur, prev)
        return f"({op}{value:{fmt}}{suffix})" if value != 0 else None

    pc_change = _fmt_change(statistics.play_count, n_pc)
    hits_change = _fmt_change(statistics.total_hits, n_count)
    ranked_score_change = _fmt_change(statistics.ranked_score, n_ranked_score)
    total_score_change = _fmt_change(statistics.total_score, n_total_score)
    gc = statistics.grade_counts
    xh_change = _fmt_change(gc.ssh, n_xh)
    x_change = _fmt_change(gc.ss, n_x)
    sh_change = _fmt_change(gc.sh, n_sh)
    s_change = _fmt_change(gc.s, n_s)
    a_change = _fmt_change(gc.a, n_a)
    play_time_change = _fmt_change(statistics.play_time, n_play_time, suffix="s")
    cur_badge = len(info.badges) if info.badges else 0
    badge_count_change = _fmt_change(cur_badge, n_badge_count)
    badges = [Badge(**i.model_dump()) for i in info.badges] if info.badges else None

    def build_best_play(score) -> DrawBestPlay | None:
        if not score.beatmap:
            return None
        osu_file = map_path / str(score.beatmap.set_id) / f"{score.beatmap.id}.osu"
        stars = score.beatmap.stars
        if _has_star_rating_mod(score) and osu_file.exists():
            try:
                stars = cal_stars(score, str(osu_file.absolute()), source)
            except Exception:
                pass
        speed_changes = get_speed_change_labels(score.mods)
        mods = [mod.acronym for mod in score.mods]
        if "NC" in mods and "DT" in mods:
            mods.remove("DT")
        cover_url = (
            score.beatmapset.covers.list
            if score.beatmapset and score.beatmapset.covers
            else f"https://assets.ppy.sh/beatmaps/{score.beatmap.set_id}/covers/list@2x.jpg"
        )
        return DrawBestPlay(
            title=score.beatmap.title,
            artist=score.beatmap.artist,
            version=score.beatmap.version,
            cover_url=cover_url,
            pp=score.pp or 0,
            accuracy=score.accuracy,
            stars=stars,
            rank=score.rank,
            mods=mods,
            speed_changes=speed_changes,
            ended_at=score.ended_at,
        )

    prepared_plays = await asyncio.gather(*(asyncio.to_thread(build_best_play, score) for score in scores))
    best_plays = [play for play in prepared_plays if play is not None]

    rank_history = (info.rank_history or {}).get("data", [])
    draw_user = DrawUser(
        id=info.id,
        username=info.username,
        avatar_url=info.avatar_url,
        country_code=info.country_code,
        support_level=info.support_level,
        join_date=info.join_date,
        follower_count=info.follower_count,
        achievement_count=len(info.user_achievements or []),
        rank_history=rank_history,
        best_plays=best_plays,
        mode=mode.upper(),
        badges=badges,
        team=info.team.model_dump() if info.team else None,
        statistics=info.statistics.model_dump() if info.statistics else None,
        footer=footer,
        rank_change=rank_change,
        country_rank_change=country_rank_change,
        pp_change=pp_change,
        acc_change=acc_change,
        pc_change=pc_change,
        hits_change=hits_change,
        ranked_score_change=ranked_score_change,
        total_score_change=total_score_change,
        xh_change=xh_change,
        x_change=x_change,
        sh_change=sh_change,
        s_change=s_change,
        a_change=a_change,
        play_time_change=play_time_change,
        badge_count_change=badge_count_change,
    )
    avatar_data = avatar_data if isinstance(avatar_data, str) else None
    team_data = team_data if isinstance(team_data, str) else None
    draw_data = draw_user.model_dump(mode="json")
    draw_data["avatar_data"] = avatar_data
    draw_data["background_data"] = bg or None
    if draw_data.get("team"):
        draw_data["team"]["flag_data"] = team_data
    for badge_data, badge in zip(draw_data.get("badges") or [], visible_badges):
        cache_path = badge_cache_file(badge)
        badge_data["image_data"] = file_data_uri(cache_path) if cache_path.exists() else None
    for play_data, cover_path in zip(draw_data.get("best_plays") or [], cover_paths):
        play_data["cover_data"] = (
            thumbnail_data_uri(cover_path, max_width=196, max_height=104) if cover_path.exists() else None
        )
    image = (await render_info_svg(draw_data)).getvalue()
    if return_info:
        return image, info
    return image
