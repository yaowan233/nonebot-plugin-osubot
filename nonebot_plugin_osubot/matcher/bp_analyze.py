from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from nonebot import on_command
from nonebot.typing import T_State


from .utils import split_msg
from ..utils import NGM
from ..schema import Score
from ..api import safe_async_get, osu_api

bp_analyze = on_command("bpa", aliases={"bp分析"}, priority=11, block=True)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
rank_color = {
    "X": "#ffe193",
    "XH": "#ffe193",
    "S": "#ffe193",
    "SH": "#ffe193",
    "A": "#88da20",
    "B": "#e9b941",
    "C": "#fa8a59",
    "D": "#f55757",
}


@bp_analyze.handle(parameterless=[split_msg()])
async def _(state: T_State):
    user = state["para"] if state["para"] else state["user"]
    bp_info = await osu_api("bp", user, NGM[state["mode"]], is_name=state["is_name"])
    if not bp_info:
        return f'未查询到在 {NGM[state["mode"]]} 的游玩记录'
    if isinstance(bp_info, str):
        return bp_info
    score_ls = [Score(**i) for i in bp_info]
    song_length = pd.Series([i.beatmap.total_length for i in score_ls])
    colors = [rank_color[i.rank] for i in score_ls]
    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx()
    # 绘制柱状图
    ax1.bar(
        range(len(song_length)), song_length, color=colors, width=0.8, align="center"
    )
    # 添加柱状图边框
    for num, (i, j) in enumerate(zip(range(len(song_length)), song_length)):
        if score_ls[num].rank in ("X", "XH"):
            rect = plt.Rectangle(
                (i - 0.4, 0), 0.8, j, edgecolor="yellow", facecolor="none", linewidth=2
            )
            ax1.add_patch(rect)
    # 设置 y 轴刻度为 xx:xx 的格式
    ax2.plot([i.pp for i in score_ls])
    ax1.yaxis.set_major_locator(ticker.MultipleLocator(base=60))  # 设置主刻度为每分钟
    ax1.yaxis.set_major_formatter(
        ticker.FuncFormatter(lambda x, pos: f"{x // 60:.0f}分钟")
    )
    plt.show()
    # 统计mods pp
    mods_pp = defaultdict(int)
    for num, i in enumerate(score_ls):
        if not i.mods:
            mods_pp["NM"] += i.pp * 0.95**num
        for j in i.mods:
            mods_pp[j] += i.pp * 0.95**num
    plt.pie(mods_pp.values(), labels=mods_pp.keys())
    legend_labels = [
        f"{label}: {size:.0f}pp"
        for label, size in zip(mods_pp.keys(), mods_pp.values())
    ]
    plt.legend(legend_labels, loc="upper right")
    plt.show()
