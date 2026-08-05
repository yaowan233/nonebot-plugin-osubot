from pathlib import Path
from typing import Any

import jinja2

from .browser import persistent_page, wait_for_page_assets

template_path = Path(__file__).parent / "rank_templates"


def prepare_rank_display(players: list[dict[str, Any]], requester_osu_id: int | None) -> dict[str, Any]:
    """Select the top 20 and pin the requester when they rank below the fold."""
    ranked = sorted(
        (player for player in players if player["pp"] >= 100),
        key=lambda player: player["pp"],
        reverse=True,
    )
    for place, player in enumerate(ranked, start=1):
        player["place"] = place
        player["is_self"] = player["osu_id"] == requester_osu_id

    visible = ranked[:20]
    requester = next((player for player in ranked if player["is_self"]), None)
    pinned = requester if requester and requester["place"] > 20 else None
    return {
        "total_count": len(ranked),
        "podium": [ranked[index] for index in (1, 0, 2) if index < len(ranked)],
        "visible": visible,
        "rows": visible[3:],
        "pinned": pinned,
        "hidden_start": 21,
        "hidden_end": pinned["place"] - 1 if pinned else None,
    }


async def draw_group_rank(
    players: list[dict[str, Any]],
    requester_osu_id: int | None,
    mode_name: str,
    updated_at: str,
) -> bytes:
    data = prepare_rank_display(players, requester_osu_id)
    data.update({"mode_name": mode_name, "updated_at": updated_at})
    template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(str(template_path)), enable_async=True
    ).get_template("index.html")
    async with persistent_page("rank", (template_path / "index.html").as_uri(), {"width": 1280, "height": 900}) as page:
        await page.set_content(await template.render_async(**data), wait_until="domcontentloaded")
        await wait_for_page_assets(page)
        element = await page.query_selector(".rank")
        assert element
        return await element.screenshot(type="png")
