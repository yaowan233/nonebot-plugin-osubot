from collections import defaultdict

from nonebot import on_command
from nonebot.internal.adapter import Event
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from ..database import UserData
from ..draw.echarts import draw_bpa_plot
from ..draw.score import cal_score_info
from ..utils import NGM
from ..schema import NewScore
from ..api import osu_api, get_users

bp_analyze = on_command("bpa", aliases={"bp分析"}, priority=11, block=True)
rank_color = {
    "X": "#ffc83a",
    "XH": "#c7eaf5",
    "S": "#ffc83a",
    "SH": "#c7eaf5",
    "A": "#84d61c",
    "B": "#e9b941",
    "C": "#fa8a59",
    "D": "#f55757",
}


@bp_analyze.handle(parameterless=[split_msg()])
async def _(event: Event, state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    user = state["para"] if state["para"] else state["user"]
    bp_info = await osu_api("bp", user, NGM[state["mode"]], is_name=state["is_name"])
    if not bp_info:
        await UniMessage.text(f'未查询到 {user} 在 {NGM[state["mode"]]} 的游玩记录').finish(reply_to=True)
    if isinstance(bp_info, str):
        await UniMessage.text(bp_info).finish(reply_to=True)
    user = await UserData.get_or_none(user_id=event.get_user_id())
    score_ls = [NewScore(**i) for i in bp_info]
    for score in score_ls:
        if {"acronym": "DT"} in score.mods or {"acronym": "NC"} in score.mods:
            score.beatmap.total_length /= 1.5
        if {"acronym": "HT"} in score.mods:
            score.beatmap.total_length /= 0.75
    score_ls = [cal_score_info(user.lazer_mode, score) for score in score_ls]
    pp_ls = [round(i.pp, 0) for i in score_ls]
    length_ls = []
    for i in score_ls:
        if i.rank == "XH":
            length_ls.append(
                {
                    "value": i.beatmap.total_length,
                    "itemStyle": {"color": rank_color[i.rank], "shadowBlur": 8, "shadowColor": "#b4ffff"},
                }
            )
        elif i.rank == "X":
            length_ls.append(
                {
                    "value": i.beatmap.total_length,
                    "itemStyle": {"color": rank_color[i.rank], "shadowBlur": 8, "shadowColor": "#ffff00"},
                }
            )
        else:
            length_ls.append({"value": i.beatmap.total_length, "itemStyle": {"color": rank_color[i.rank]}})
    mods_pp = defaultdict(int)
    for num, i in enumerate(score_ls):
        if not i.mods:
            mods_pp["NM"] += i.pp * 0.95**num
        for j in i.mods:
            mods_pp[j["acronym"]] += i.pp * 0.95**num
    pp_data = []
    for mod, pp in mods_pp.items():
        pp_data.append({"name": mod, "value": round(pp, 2)})
    mapper_pp = defaultdict(int)
    for num, i in enumerate(score_ls):
        mapper_pp[i.beatmap.user_id] += i.pp * 0.95**num
    mapper_pp = sorted(mapper_pp.items(), key=lambda x: x[1], reverse=True)
    mapper_pp = mapper_pp[:10]
    users = await get_users([i[0] for i in mapper_pp])
    user_dic = {i.id: i.username for i in users}
    mapper_pp_data = []
    for mapper, pp in mapper_pp:
        mapper_pp_data.append({"name": user_dic.get(mapper, ""), "value": round(pp, 2)})
    if len(mapper_pp_data) > 20:
        mapper_pp_data = mapper_pp_data[:20]
    name = f'{score_ls[0].user.username} {NGM[state["mode"]]} 模式 '
    byt = await draw_bpa_plot(name, pp_ls, length_ls, pp_data, mapper_pp_data)
    await (UniMessage.image(raw=byt)).finish(reply_to=True)
