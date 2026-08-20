from nonebot.log import logger
from nonebot_plugin_orm import get_session

from ..utils import FGM
from ..api import get_osu_user, get_users
from ..database.models import UserData
from .snapshot import info_snapshot_store


async def bind_user_info(project: str, uid, qid) -> str:
    info = await get_osu_user(str(uid))
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
    msg = f"成功绑定 {name}\n默认模式为 {playmode}，可使用 /mode o、t、c、m 切换"
    return msg


async def update_users_info(uids: list[int]) -> int:
    users = await get_users(uids)
    updated = await info_snapshot_store.save(users)
    if users:
        logger.info(f"批量更新玩家信息完成: 请求 {len(uids)}，返回 {len(users)}，写入 {updated}")
    return updated
