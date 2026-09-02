"""Native SVG renderer for achievement grids."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

import math

from .svg_components import fitted_text, image, text
from .svg_render import render_svg_jpeg_async


WIDTH = 1280
HEADER_HEIGHT = 150
GRID_TOP = 22
GRID_MARGIN = 40
GRID_GAP = 14
COLUMNS = 5
CARD_HEIGHT = 136
FOOTER_SPACE = 60
MIN_HEIGHT = 900
CARD_WIDTH = (WIDTH - GRID_MARGIN * 2 - GRID_GAP * (COLUMNS - 1)) / COLUMNS

BG = "#101722"
CARD_BG = "#0b1925"
PINK = "#ec3f83"
CYAN = "#62cddd"
GOLD = "#f3b61f"
MUTED = "#82929d"
DIM = "#586b78"


def _height(count: int) -> int:
    rows = math.ceil(count / COLUMNS) if count else 0
    grid_height = rows * CARD_HEIGHT + max(0, rows - 1) * GRID_GAP
    return max(MIN_HEIGHT, round(HEADER_HEIGHT + GRID_TOP + grid_height + FOOTER_SPACE))


def _placeholder_icon(cx: float, cy: float) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="34" fill="#152838" stroke="#ffffff" stroke-opacity=".1"/>'
        f'<path d="M{cx} {cy - 17}l5.2 10.6 11.7 1.7-8.5 8.2 2 11.6L{cx} {cy + 26.6}l-10.4 5.5 2-11.6-8.5-8.2 11.7-1.7z" fill="{GOLD}" fill-opacity=".7"/>'
    )


def _achievement_card(row: dict, index: int) -> str:
    column = index % COLUMNS
    line = index // COLUMNS
    x = GRID_MARGIN + column * (CARD_WIDTH + GRID_GAP)
    y = HEADER_HEIGHT + GRID_TOP + line * (CARD_HEIGHT + GRID_GAP)
    cx = x + CARD_WIDTH / 2
    icon_x = cx - 36
    icon_y = y + 12
    clip_id = f"achievement-icon-{index}"
    icon_data = row.get("icon_data")
    icon_markup = (
        f'<defs><clipPath id="{clip_id}"><rect x="{icon_x}" y="{icon_y}" width="72" height="72" rx="8"/></clipPath></defs>'
        + image(icon_data, icon_x, icon_y, 72, 72, clip=clip_id, contain=True)
        if icon_data
        else _placeholder_icon(cx, icon_y + 36)
    )
    grouping = row.get("grouping") or "成就"
    achieved_at = row.get("achieved_at") or ""
    return f"""<g data-role="achievement-card"><rect x="{x}" y="{y}" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="10" fill="{CARD_BG}" fill-opacity=".92" stroke="#ffffff" stroke-opacity=".075"/>
{icon_markup}{fitted_text(cx, y + 104, row.get("name") or "未命名成就", 13, CARD_WIDTH - 20, anchor="middle", weight=700)}
{fitted_text(cx, y + 121, grouping, 10, CARD_WIDTH - 20, fill=GOLD, anchor="middle", weight=700)}
{fitted_text(cx, y + 132, achieved_at, 9, CARD_WIDTH - 20, fill=MUTED, anchor="middle") if achieved_at else ""}</g>"""


def build_achievement_svg(payload: dict) -> tuple[str, int]:
    achievements = list(payload.get("achievements") or [])
    height = _height(len(achievements))
    avatar = payload.get("me_avatar_data")
    avatar_markup = image(avatar, 48, 36, 78, 78, clip="achievement-avatar")
    cards = "".join(_achievement_card(row, index) for index, row in enumerate(achievements))
    range_text = f"{int(payload.get('start') or 0)}-{int(payload.get('end') or 0)}"
    return (
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<defs><linearGradient id="achievement-head" x1="0" y1="0" x2="1" y2=".4"><stop stop-color="#1a2c3e"/><stop offset=".7" stop-color="{BG}"/></linearGradient><radialGradient id="achievement-glow" cx="82%" cy="0" r="58%"><stop stop-color="#8d3267" stop-opacity=".22"/><stop offset="1" stop-color="#8d3267" stop-opacity="0"/></radialGradient><pattern id="achievement-grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="#ffffff" stroke-opacity=".025"/></pattern><clipPath id="achievement-avatar"><circle cx="87" cy="75" r="39"/></clipPath></defs>
<rect width="{WIDTH}" height="{height}" fill="{BG}"/><rect width="{WIDTH}" height="{height}" fill="url(#achievement-grid)"/><rect width="{WIDTH}" height="{HEADER_HEIGHT}" fill="url(#achievement-head)"/><rect width="{WIDTH}" height="{HEADER_HEIGHT}" fill="url(#achievement-glow)"/>
<circle cx="87" cy="75" r="39" fill="#26323d"/>{avatar_markup}<circle cx="87" cy="75" r="40.5" fill="none" stroke="{GOLD}" stroke-width="3"/>
{fitted_text(144, 69, payload.get("title") or "成就列表", 30, 780, weight=800)}{fitted_text(144, 92, payload.get("subtitle") or "", 12, 800, fill=MUTED, weight=600)}
{text(1232, 58, range_text, 16, fill=CYAN, anchor="end", weight=800)}{text(1232, 78, f"/ {int(payload.get('total') or 0)}", 12, fill=MUTED, anchor="end", weight=600)}{text(1232, 99, "OSU! ACHIEVEMENTS", 10, fill=MUTED, anchor="end", weight=700)}
<line x1="0" y1="149.5" x2="1280" y2="149.5" stroke="#ffffff" stroke-opacity=".07"/>{cards}
{text(40, height - 20, "OSUBOT ACHIEVEMENTS · /ma /ar", 10, fill=DIM, weight=700)}{fitted_text(1240, height - 20, payload.get("me_name") or "", 10, 400, fill=DIM, anchor="end", weight=700)}
</svg>""",
        height,
    )


async def render_achievement_svg(payload: dict) -> bytes:
    svg, height = build_achievement_svg(payload)
    result = await render_svg_jpeg_async(svg, width=WIDTH, height=height, quality=92)
    return result.getvalue()
