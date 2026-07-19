from collections import defaultdict
from pathlib import Path
from typing import Any

from nonebot_plugin_htmlrender import template_to_pic

from ..api import get_users

template_path = str(Path(__file__).parent / "templates")

RANK_COLORS = {
    "X": "#ffc83a",
    "XH": "#c7eaf5",
    "S": "#ffc83a",
    "SH": "#c7eaf5",
    "A": "#84d61c",
    "B": "#e9b941",
    "C": "#fa8a59",
    "D": "#f55757",
}


async def draw_history_plot(pp_ls, date_ls, rank_ls, title) -> bytes:
    template_name = "pp_rank_line_chart.html"
    pic = await template_to_pic(
        template_path,
        template_name,
        {"pp_ls": pp_ls, "date_ls": date_ls, "rank_ls": rank_ls, "title": title},
    )
    return pic


async def build_bpa_data(score_ls, source: str) -> dict[str, Any]:
    pp_values = [float(score.pp or 0) for score in score_ls]
    pp_ls = [round(pp, 0) for pp in pp_values]

    length_ls = []
    lengths = []
    for score in score_ls:
        beatmap = getattr(score, "beatmap", None)
        if beatmap is None:
            continue
        length = float(beatmap.total_length or 0)
        lengths.append(length)
        item_style = {"color": RANK_COLORS.get(score.rank, "#ffffff")}
        if score.rank == "XH":
            item_style.update({"shadowBlur": 8, "shadowColor": "#b4ffff"})
        elif score.rank == "X":
            item_style.update({"shadowBlur": 8, "shadowColor": "#ffff00"})
        length_ls.append({"value": length, "itemStyle": item_style})

    mods_pp: defaultdict[str, float] = defaultdict(float)
    mapper_pp: defaultdict[Any, float] = defaultdict(float)
    for index, score in enumerate(score_ls):
        weighted_pp = float(score.pp or 0) * 0.95**index
        mods = score.mods or []
        if not mods:
            mods_pp["NM"] += weighted_pp
        for mod in mods:
            mods_pp[mod.acronym] += weighted_pp

        beatmap = getattr(score, "beatmap", None)
        if beatmap is not None:
            mapper = beatmap.creator if source == "ppysb" else beatmap.user_id
            mapper_pp[mapper] += weighted_pp

    mod_pp_ls = [
        {"name": mod, "value": round(pp, 2)}
        for mod, pp in sorted(mods_pp.items(), key=lambda item: item[1], reverse=True)
    ]
    mapper_items = sorted(mapper_pp.items(), key=lambda item: item[1], reverse=True)[:9]
    if source == "ppysb":
        mapper_pp_ls = [{"name": str(mapper), "value": round(pp, 2)} for mapper, pp in mapper_items]
    else:
        users = await get_users([mapper for mapper, _ in mapper_items]) if mapper_items else []
        usernames = {user.id: user.username for user in users}
        mapper_pp_ls = [
            {"name": usernames.get(mapper, str(mapper)), "value": round(pp, 2)} for mapper, pp in mapper_items
        ]

    stats = {
        "count": len(score_ls),
        "average_pp": round(sum(pp_values) / len(pp_values), 2) if pp_values else 0,
        "max_pp": round(max(pp_values), 2) if pp_values else 0,
        "average_length": round(sum(lengths) / len(lengths), 2) if lengths else 0,
    }
    return {
        "pp_ls": pp_ls,
        "length_ls": length_ls,
        "mod_pp_ls": mod_pp_ls,
        "mapper_pp_ls": mapper_pp_ls,
        "stats": stats,
    }


async def draw_bpa_plot(name, pp_ls, length_ls, mod_pp_ls, mapper_pp_ls, stats=None) -> bytes:
    template_name = "bpa_chart.html"
    pic = await template_to_pic(
        template_path,
        template_name,
        {
            "name": name,
            "pp_ls": pp_ls,
            "length_ls": length_ls,
            "mod_pp_ls": mod_pp_ls,
            "mapper_pp_ls": mapper_pp_ls,
            "length": len(pp_ls),
            "stats": stats or {},
        },
    )
    return pic


# async def draw_strains_plot(time, strains) -> bytes:
#     template_name = "basic_line_chart.html"
#     pic = await template_to_pic(
#         template_path,
#         template_name,
#         {"time": time, "strains": strains},
#     )
#     return pic
