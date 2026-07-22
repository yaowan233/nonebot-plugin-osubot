import datetime

from nonebot import on_command
from nonebot.params import T_State
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import get_session
from nonebot_plugin_uninfo import QryItrface, Uninfo
from sqlalchemy import and_, func, select

from ..database.models import InfoData, UserData
from ..draw.rank import draw_group_rank
from ..utils import NGM
from .utils import split_msg


group_pp_rank = on_command("群内排名", aliases={"rank"}, priority=11, block=True)


@group_pp_rank.handle(parameterless=[split_msg()])
async def _(
    state: T_State,
    session: Uninfo,
    interface: QryItrface,
):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)

    if session is None or interface is None:
        await UniMessage.text("当前平台无法获取会话信息").finish(reply_to=True)
    scene = session.scene.parent or session.scene
    if scene.is_private:
        await UniMessage.text("群内排名只能在群组或频道中使用").finish(reply_to=True)

    members = await interface.get_members(scene.type, scene.id)
    if not members:
        await UniMessage.text("当前平台无法获取群成员列表").finish(reply_to=True)

    mode = int(state["mode"])
    member_names = {
        member.user.id: member.nick or member.user.nick or member.user.name or "" for member in members
    }
    member_ids = list(member_names)
    today = datetime.date.today()

    async with get_session() as session:
        user_data = (await session.scalars(select(UserData).where(UserData.user_id.in_(member_ids)))).all()
        bound_osu_ids = list({user.osu_id for user in user_data})
        if not bound_osu_ids:
            await UniMessage.text("本群还没有已绑定 osu! 账号的成员").finish(reply_to=True)

        current_infos = (
            await session.scalars(
                select(InfoData)
                .where(
                    InfoData.osu_id.in_(bound_osu_ids),
                    InfoData.osu_mode == mode,
                    InfoData.date == today,
                    InfoData.pp >= 100,
                )
                .order_by(InfoData.pp.desc())
            )
        ).all()

        latest_dates = (
            select(InfoData.osu_id.label("osu_id"), func.max(InfoData.date).label("latest_date"))
            .where(
                InfoData.osu_id.in_(bound_osu_ids),
                InfoData.osu_mode == mode,
                InfoData.date < today,
            )
            .group_by(InfoData.osu_id)
            .subquery()
        )
        previous_infos = (
            await session.scalars(
                select(InfoData)
                .join(
                    latest_dates,
                    and_(InfoData.osu_id == latest_dates.c.osu_id, InfoData.date == latest_dates.c.latest_date),
                )
                .where(InfoData.osu_mode == mode)
            )
        ).all()

    user_by_osu = {}
    for user in user_data:
        user_by_osu.setdefault(user.osu_id, user)
    previous_by_osu = {info.osu_id: info for info in previous_infos}
    requester = next((user for user in user_data if user.user_id == session.user.id), None)

    players = []
    seen = set()
    for info in current_infos:
        if info.osu_id in seen or info.osu_id not in user_by_osu:
            continue
        seen.add(info.osu_id)
        user = user_by_osu[info.osu_id]
        previous = previous_by_osu.get(info.osu_id)
        players.append(
            {
                "osu_id": info.osu_id,
                "osu_name": user.osu_name,
                "qq_name": member_names.get(user.user_id, ""),
                "avatar_url": f"https://a.ppy.sh/{info.osu_id}",
                "pp": info.pp,
                "global_rank": info.g_rank,
                "delta": info.pp - previous.pp if previous else None,
            }
        )

    if not players:
        await UniMessage.text(f"今天还没有 {NGM[str(mode)]} 模式的群排名数据").finish(reply_to=True)

    image = await draw_group_rank(
        players,
        requester.osu_id if requester else None,
        f"{NGM[str(mode)]}模式",
        datetime.datetime.now().strftime("%Y/%m/%d %H:%M"),
    )
    await UniMessage.image(raw=image).finish(reply_to=True)
