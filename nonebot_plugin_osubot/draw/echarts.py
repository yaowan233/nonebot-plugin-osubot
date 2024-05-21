from pathlib import Path

from nonebot_plugin_htmlrender import template_to_pic


async def draw_history_plot(pp_ls, date_ls, rank_ls, title) -> bytes:
    template_path = str(Path(__file__).parent / "templates")
    template_name = "pp_rank_line_chart.html"
    pic = await template_to_pic(
        template_path,
        template_name,
        {"pp_ls": pp_ls, "date_ls": date_ls, "rank_ls": rank_ls, "title": title},
    )
    return pic
