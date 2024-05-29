from datetime import date
from nonebot.log import logger
from ..utils import GM, FGM
from ..database.models import UserData, InfoData
from ..api import osu_api, get_users


async def bind_user_info(project: str, uid, qid, is_name) -> str:
    info = await osu_api(project, uid, GM[0], is_name=is_name)
    if not info:
        return f"未查询到玩家“{uid}”，请检查是否有多于或缺少的空格"
    elif isinstance(info, str):
        return info
    uid = info["id"]
    name = info["username"]
    playmode = info["playmode"]
    await UserData.create(user_id=qid, osu_id=uid, osu_name=name, osu_mode=FGM[playmode])
    await update_users_info([uid])
    msg = f"用户 {name} 已成功绑定QQ {qid}\n默认模式为std，若更改模式至mania请输入/更新模式 3"
    return msg


async def update_users_info(uids: list[int]):
    users = await get_users(uids)
    for user in users:
        if await InfoData.filter(osu_id=user.id, date=date.today()).first():
            continue
        if not user.statistics_rulesets.osu:
            await InfoData.create(
                osu_id=user.id,
                c_rank=0,
                g_rank=0,
                pp=0,
                acc=0,
                pc=0,
                count=0,
                osu_mode=0,
                date=date.today(),
            )
        elif not user.statistics_rulesets.taiko:
            await InfoData.create(
                osu_id=user.id,
                c_rank=0,
                g_rank=0,
                pp=0,
                acc=0,
                pc=0,
                count=0,
                osu_mode=1,
                date=date.today(),
            )
        elif not user.statistics_rulesets.fruits:
            await InfoData.create(
                osu_id=user.id,
                c_rank=0,
                g_rank=0,
                pp=0,
                acc=0,
                pc=0,
                count=0,
                osu_mode=2,
                date=date.today(),
            )
        elif not user.statistics_rulesets.mania:
            await InfoData.create(
                osu_id=user.id,
                c_rank=0,
                g_rank=0,
                pp=0,
                acc=0,
                pc=0,
                count=0,
                osu_mode=3,
                date=date.today(),
            )
        elif user.statistics_rulesets.osu:
            await InfoData.create(
                osu_id=user.id,
                c_rank=user.statistics_rulesets.country_rank,
                g_rank=user.statistics_rulesets.global_rank,
                pp=user.statistics_rulesets.pp,
                acc=user.statistics_rulesets.hit_accuracy,
                pc=user.statistics_rulesets.play_count,
                count=user.statistics_rulesets.total_hits,
                osu_mode=0,
                date=date.today(),
            )
        elif user.statistics_rulesets.taiko:
            await InfoData.create(
                osu_id=user.id,
                c_rank=user.statistics_rulesets.country_rank,
                g_rank=user.statistics_rulesets.global_rank,
                pp=user.statistics_rulesets.pp,
                acc=user.statistics_rulesets.hit_accuracy,
                pc=user.statistics_rulesets.play_count,
                count=user.statistics_rulesets.total_hits,
                osu_mode=1,
                date=date.today(),
            )
        elif user.statistics_rulesets.fruits:
            await InfoData.create(
                osu_id=user.id,
                c_rank=user.statistics_rulesets.country_rank,
                g_rank=user.statistics_rulesets.global_rank,
                pp=user.statistics_rulesets.pp,
                acc=user.statistics_rulesets.hit_accuracy,
                pc=user.statistics_rulesets.play_count,
                count=user.statistics_rulesets.total_hits,
                osu_mode=2,
                date=date.today(),
            )
        elif user.statistics_rulesets.mania:
            await InfoData.create(
                osu_id=user.id,
                c_rank=user.statistics_rulesets.country_rank,
                g_rank=user.statistics_rulesets.global_rank,
                pp=user.statistics_rulesets.pp,
                acc=user.statistics_rulesets.hit_accuracy,
                pc=user.statistics_rulesets.play_count,
                count=user.statistics_rulesets.total_hits,
                osu_mode=3,
                date=date.today(),
            )
        user_info = await UserData.filter(osu_id=user.id).first()
        if user_info.osu_name != user.username:
            user_info.osu_name = user.username
            await user_info.save()
        logger.info(f"玩家:[{user.uid}] 个人信息更新完毕")
