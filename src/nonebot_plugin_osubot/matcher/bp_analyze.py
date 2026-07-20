from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..utils import NGM
from .utils import split_msg
from ..database import UserData
from ..api import get_user_scores
from ..exceptions import NetworkError
from ..draw.score import cal_score_info
from ..draw.echarts import build_bpa_data, draw_bpa_plot

bp_analyze = on_command("bpa", aliases={"bp分析"}, priority=11, block=True)


@bp_analyze.handle(parameterless=[split_msg()])
async def _(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    async with get_session() as session:
        user = await session.scalar(select(UserData).where(UserData.user_id == event.get_user_id()))
    uid = state["user"]
    lazer_mode = "lazer模式下" if state["is_lazer"] else "stable模式下"
    try:
        score_ls = await get_user_scores(
            uid, NGM[state["mode"]], "best", state["source"], legacy_only=not state["is_lazer"]
        )
    except NetworkError as e:
        await UniMessage.text(
            f"在查找用户：{state['username']} {NGM[state['mode']]}模式 {lazer_mode}时 {str(e)}"
        ).finish(reply_to=True)
    for score in score_ls:
        if not state["is_lazer"] or state["source"] == "ppysb":
            score.mods = [mod for mod in score.mods if mod.acronym != "CL"]
        for mod in score.mods:
            if mod.acronym == "DT" or mod.acronym == "NC":
                score.beatmap.total_length /= 1.5
            if mod.acronym == "HT":
                score.beatmap.total_length /= 0.75
    score_ls = [cal_score_info(user.lazer_mode, score) for score in score_ls]
    data = await build_bpa_data(score_ls, state["source"])
    name = f"{state['username']} {NGM[state['mode']]} 模式"
    byt = await draw_bpa_plot(name, **data)
    await UniMessage.image(raw=byt).finish(reply_to=True)
