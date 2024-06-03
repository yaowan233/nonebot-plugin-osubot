from pathlib import Path

from nonebot_plugin_htmlrender import template_to_pic

template_path = str(Path(__file__).parent / "templates")


async def draw_history_plot(pp_ls, date_ls, rank_ls, title) -> bytes:
    template_name = "pp_rank_line_chart.html"
    pic = await template_to_pic(
        template_path,
        template_name,
        {"pp_ls": pp_ls, "date_ls": date_ls, "rank_ls": rank_ls, "title": title},
    )
    return pic


async def draw_bpa_plot(name, pp_ls, length_ls, mod_pp_ls, mapper_pp_ls) -> bytes:
    template_name = "bpa_chart.html"
    pic = await template_to_pic(
        template_path,
        template_name,
        {"name": name, "pp_ls": pp_ls, "length_ls": length_ls, "mod_pp_ls": mod_pp_ls, "mapper_pp_ls": mapper_pp_ls},
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
