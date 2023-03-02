from nonebot.log import logger
from ..utils import GM
from ..database.models import UserData, InfoData
from ..schema import User
from ..api import osu_api


async def bind_user_info(project: str, uid, qid) -> str:
    info = await osu_api(project, uid, GM[0])
    if not info:
        return f'未查询到玩家“{uid}”，请检查是否有多于或缺少的空格'
    elif isinstance(info, str):
        return info
    uid = info['id']
    name = info['username']
    await UserData.create(user_id=qid, osu_id=uid, osu_name=name, osu_mode=0)
    await update_user_info(uid)
    msg = f'用户 {name} 已成功绑定QQ {qid}'
    return msg


async def update_user_info(uid: int):
    for mode in range(4):
        userinfo_dic = await osu_api('update', uid, GM[mode])
        userinfo = User(**userinfo_dic)
        if userinfo.statistics.play_count != 0:
            if info := await InfoData.filter(osu_id=uid, osu_mode=mode).first():
                info.c_rank = userinfo.statistics.country_rank
                info.g_rank = userinfo.statistics.global_rank
                info.pp = userinfo.statistics.pp
                info.acc = round(userinfo.statistics.hit_accuracy, 2)
                info.pc = userinfo.statistics.play_count
                info.count = userinfo.statistics.total_hits
            else:
                info = InfoData(osu_id=uid,
                                c_rank=userinfo.statistics.country_rank,
                                g_rank=userinfo.statistics.global_rank,
                                pp=userinfo.statistics.pp,
                                acc=round(userinfo.statistics.hit_accuracy, 2),
                                pc=userinfo.statistics.play_count,
                                count=userinfo.statistics.total_hits,
                                osu_mode=mode)
        else:
            if info := await InfoData.filter(osu_id=uid, osu_mode=mode).first():
                info.c_rank = userinfo.statistics.country_rank
                info.g_rank = userinfo.statistics.global_rank
                info.pp = userinfo.statistics.pp
                info.acc = round(userinfo.statistics.hit_accuracy, 2)
                info.pc = userinfo.statistics.play_count
                info.count = userinfo.statistics.total_hits
            else:
                info = InfoData(osu_id=uid,
                                c_rank=0,
                                g_rank=0,
                                pp=0,
                                acc=0,
                                pc=0,
                                count=0,
                                osu_mode=mode)
        await info.save()
        logger.info(f'玩家:[{userinfo.username}] {GM[mode]}模式 个人信息更新完毕')
