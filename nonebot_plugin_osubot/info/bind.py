from datetime import date
from nonebot.log import logger
from ..utils import GM, FGM
from ..database.models import UserData, InfoData
from ..schema import User
from ..api import osu_api


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
    await update_user_info(uid)
    msg = f"用户 {name} 已成功绑定 {qid}\n默认模式为 {playmode}，如若更改模式至 mania 请输入/更新模式 3"
    return msg


async def update_user_info(uid: int):
    for mode in range(4):
        userinfo_dic = await osu_api("update", uid, GM[mode])
        if isinstance(userinfo_dic, str):
            logger.warning(f"获取uid{uid} 更新信息出错\n {userinfo_dic}")
            continue
        userinfo = User(**userinfo_dic)
        if await InfoData.filter(osu_id=uid, osu_mode=mode, date=date.today()).first():
            continue
        elif userinfo.statistics.play_count:
            await InfoData.create(
                osu_id=uid,
                c_rank=userinfo.statistics.country_rank,
                g_rank=userinfo.statistics.global_rank,
                pp=userinfo.statistics.pp,
                acc=round(userinfo.statistics.hit_accuracy, 2),
                pc=userinfo.statistics.play_count,
                count=userinfo.statistics.total_hits,
                osu_mode=mode,
                date=date.today(),
            )
        else:
            await InfoData.create(
                osu_id=uid,
                c_rank=0,
                g_rank=0,
                pp=0,
                acc=0,
                pc=0,
                count=0,
                osu_mode=mode,
                date=date.today(),
            )
    logger.info(f"玩家:[{uid}] 个人信息更新完毕")
