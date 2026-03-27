from datetime import date

from nonebot.log import logger
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..utils import GM, FGM
from ..api import osu_api, get_users
from ..database.models import InfoData, UserData


async def bind_user_info(project: str, uid, qid) -> str:
    info = await osu_api(project, uid, GM[0])
    if not info:
        return f'未查询到玩家"{uid}"，请检查是否有多于或缺少的空格'
    elif isinstance(info, str):
        return info
    uid = info["id"]
    name = info["username"]
    playmode = info["playmode"]
    async with get_session() as session:
        session.add(UserData(user_id=qid, osu_id=uid, osu_name=name, osu_mode=FGM[playmode]))
        await session.commit()
    await update_users_info([uid])
    msg = f"成功绑定 {name}\n默认模式为 {playmode}，若更改模式至其他模式，如 mania，请输入 /更新模式 3"
    return msg


def _make_info_data(osu_id: int, stats, osu_mode: int, badge_count: int = 0) -> InfoData:
    gc = stats.grade_counts
    return InfoData(
        osu_id=osu_id,
        c_rank=stats.country_rank,
        g_rank=stats.global_rank,
        pp=stats.pp,
        acc=stats.hit_accuracy,
        pc=stats.play_count,
        count=stats.total_hits,
        osu_mode=osu_mode,
        date=date.today(),
        ranked_score=stats.ranked_score,
        total_score=stats.total_score,
        max_combo=stats.maximum_combo,
        count_xh=gc.ssh,
        count_x=gc.ss,
        count_sh=gc.sh,
        count_s=gc.s,
        count_a=gc.a,
        replays=stats.replays_watched_by_others,
        play_time=stats.play_time,
        badge_count=badge_count,
    )


async def update_users_info(uids: list[int]):
    users = await get_users(uids)
    for user in users:
        async with get_session() as session:
            if await session.scalar(select(InfoData).where(InfoData.osu_id == user.id, InfoData.date == date.today())):
                continue
            if not user.statistics_rulesets:
                continue
            rulesets = user.statistics_rulesets
            badge_count = len(user.badges) if user.badges else 0
            mode_stats = [
                (rulesets.osu, 0),
                (rulesets.taiko, 1),
                (rulesets.fruits, 2),
                (rulesets.mania, 3),
            ]
            for stats, mode in mode_stats:
                if stats:
                    session.add(_make_info_data(user.id, stats, mode, badge_count))
                else:
                    session.add(InfoData(osu_id=user.id, c_rank=0, g_rank=0, pp=0, acc=0, pc=0, count=0, osu_mode=mode, date=date.today()))
            user_info = await session.scalar(select(UserData).where(UserData.osu_id == user.id))
            if user_info and user_info.osu_name != user.username:
                user_info.osu_name = user.username
            await session.commit()
        logger.info(f"玩家:[{user.username}] 个人信息更新完毕")
