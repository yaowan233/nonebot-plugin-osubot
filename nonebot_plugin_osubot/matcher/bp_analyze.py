from collections import defaultdict

from nonebot import on_command
from nonebot.internal.adapter import Event
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from ..database import UserData
from ..draw.echarts import draw_bpa_plot, draw_mod_pp_plot
from ..draw.score import cal_score_info
from ..utils import NGM
from ..schema import NewScore
from ..api import osu_api

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
    user = state["para"] if state["para"] else state["user"]
    bp_info = await osu_api("bp", user, NGM[state["mode"]], is_name=state["is_name"])
    if not bp_info:
        await UniMessage.text(f'未查询到在 {NGM[state["mode"]]} 的游玩记录').finish(reply_to=True)
    if isinstance(bp_info, str):
        await UniMessage.text(bp_info).finish(reply_to=True)
    user = await UserData.get_or_none(user_id=event.get_user_id())
    score_ls = [NewScore(**i) for i in bp_info]
    for score in score_ls:
        if {'acronym': 'DT'} in score.mods or {'acronym': 'NC'} in score.mods:
            score.beatmap.total_length /= 1.5
        if {'acronym': 'HT'} in score.mods:
            score.beatmap.total_length /= 0.75
    score_ls = [cal_score_info(user.lazer_mode, score) for score in score_ls]
    pp_ls = [i.pp for i in score_ls]
    length_ls = []
    for i in score_ls:
        if i.rank == "XH":
            length_ls.append({'value': i.beatmap.total_length,
                              'itemStyle': {'color': rank_color[i.rank], 'shadowBlur': 8, 'shadowColor': "#b4ffff"}})
        elif i.rank == "X":
            length_ls.append({'value': i.beatmap.total_length,
                              'itemStyle': {'color': rank_color[i.rank], 'shadowBlur': 8, 'shadowColor': "#ffff00"}})
        else:
            length_ls.append({'value': i.beatmap.total_length, 'itemStyle': {'color': rank_color[i.rank]}})
    byt = await draw_bpa_plot(pp_ls, length_ls)
    mods_pp = defaultdict(int)
    for num, i in enumerate(score_ls):
        if not i.mods:
            mods_pp["NM"] += i.pp * 0.95 ** num
        for j in i.mods:
            mods_pp[j['acronym']] += i.pp * 0.95 ** num
    pp_data = []
    for mod, pp in mods_pp.items():
        pp_data.append({'name': mod, 'value': round(pp, 2)})
    byt2 = await draw_mod_pp_plot(pp_data)
    await (UniMessage.image(raw=byt) + UniMessage.image(raw=byt2)).finish(reply_to=True)
    # # 统计mods pp
    # mods_pp = defaultdict(int)
    # for num, i in enumerate(score_ls):
    #     if not i.mods:
    #         mods_pp["NM"] += i.pp * 0.95 ** num
    #     for j in i.mods:
    #         mods_pp[j] += i.pp * 0.95 ** num
    # plt.pie(mods_pp.values(), labels=mods_pp.keys())
    # legend_labels = [
    #     f"{label}: {size:.0f}pp"
    #     for label, size in zip(mods_pp.keys(), mods_pp.values())
    # ]
    # plt.legend(legend_labels, loc="upper right")
    # plt.show()
