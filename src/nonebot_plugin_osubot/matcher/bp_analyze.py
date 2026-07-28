from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM
from .utils import split_msg
from ..api import get_user_scores
from ..exceptions import NetworkError
from ..draw.score import cal_score_info
from ..draw.echarts import build_bpa_data, draw_bpa_plot

bp_analyze = on_command("bpa", aliases={"bp分析"}, priority=11, block=True)


@bp_analyze.handle(parameterless=[split_msg()])
async def _(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    uid = state["user"]
    try:
        score_ls = await get_user_scores(
            uid, NGM[state["mode"]], "best", state["source"], legacy_only=not state["is_lazer"]
        )
    except NetworkError as e:
        await UniMessage.text(f"在查找用户：{state['username']} {NGM[state['mode']]}模式时 {str(e)}").finish(
            reply_to=True
        )
    for score in score_ls:
        if not state["is_lazer"] or state["source"] == "ppysb":
            score.mods = [mod for mod in score.mods if mod.acronym != "CL"]
        for mod in score.mods:
            if mod.acronym == "DT" or mod.acronym == "NC":
                score.beatmap.total_length /= 1.5
            if mod.acronym == "HT":
                score.beatmap.total_length /= 0.75
    score_ls = [cal_score_info(state["is_lazer"], score) for score in score_ls]
    data = await build_bpa_data(score_ls, state["source"])
    name = f"{state['username']} {NGM[state['mode']]} 模式"
    byt = await draw_bpa_plot(
        name,
        username=state["username"],
        mode=NGM[state["mode"]],
        user_id=uid,
        source=state["source"],
        **data,
    )
    await UniMessage.image(raw=byt).finish(reply_to=True)
