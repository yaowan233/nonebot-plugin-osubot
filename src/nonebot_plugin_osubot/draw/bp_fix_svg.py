"""BP-list styled renderer for theoretical full-combo reports."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from io import BytesIO

from .bp_svg import CONTENT_TOP, CYAN, PINK, WIDTH, bp_profile
from .svg_components import fitted_text, image, mod_strip, number, star_color, text
from .svg_render import render_svg_jpeg_async


MODE_NAMES = ("STANDARD", "TAIKO", "CATCH", "MANIA")
COLUMNS = 5
CARD_HEIGHT = 222
ROW_GAP = 24


def _fact(x: float, label: str, value: str, *, color: str = "#101824") -> str:
    return f'<line x1="{x}" y1="103" x2="{x}" y2="146" stroke="#c9ced1"/>{text(x + 12, 114, label, 9, fill="#168f9b", weight=700)}{text(x + 12, 139, value, 20, fill=color, weight=700)}'


def _summary(payload: dict) -> str:
    return f"""
<rect x="420" y="0" width="980" height="185" fill="#f5f1e9"/><rect x="420" y="0" width="980" height="4" fill="{CYAN}"/>
{text(485, 58, f"{MODE_NAMES[int(payload['mode'])]} / BP FIX", 11, fill="#101824", weight=700)}{text(1352, 58, f"共展示 {len(payload['entries'])} 项 · 候选 {payload['candidate_count']} 项", 11, fill="#101824", anchor="end")}
<line x1="485" y1="74" x2="1352" y2="74" stroke="#c9ced1"/>
{fitted_text(485, 126, "理论 FULL COMBO", 34, 420, fill="#101824", weight=700)}
{_fact(940, "当前总 PP", number(payload['current_pp'], 2))}{_fact(1080, "理论总 PP", number(payload['fixed_pp'], 2), color=PINK)}{_fact(1230, "加权提升", "+" + number(payload['gain'], 2), color="#218f61")}
{text(1352, 166, "保持原准确率 · 清零 miss · 补满 combo · 按 0.95 权重重排", 9, fill="#59626c", anchor="end")}
"""


def _card(entry: dict, index: int) -> str:
    gap = 15
    left = 36
    width = (WIDTH - left * 2 - gap * (COLUMNS - 1)) / COLUMNS
    row, column = divmod(index, COLUMNS)
    x = left + column * (width + gap)
    y = CONTENT_TOP + row * (CARD_HEIGHT + ROW_GAP)
    visual_height = 145
    clip_id = f"bp-fix-cover-{index}"
    star = float(entry.get("stars") or 0)
    rank = f"#{entry['old_rank']} → #{entry['new_rank']}"
    combo = f"{number(entry['combo'])}x → {number(entry['max_combo'])}x"
    pp_change = f"{number(entry['old_pp'], 1)} → {number(entry['fixed_pp'], 1)} pp"
    return f"""
<g data-role="bp-fix-entry"><defs><clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{width}" height="{visual_height}" rx="8"/></clipPath></defs>
<rect x="{x}" y="{y}" width="{width}" height="{visual_height}" rx="8" fill="#101925" stroke="#ffffff"/>{image(entry.get('cover_data'), x, y, width, visual_height, clip=clip_id)}<rect x="{x}" y="{y + 48}" width="{width}" height="{visual_height - 48}" fill="url(#bp-fix-shade)" clip-path="url(#{clip_id})"/>
<rect x="{x + 12}" y="{y + 12}" width="68" height="25" rx="13" fill="{PINK}"/>{text(x + 46, y + 29, rank, 10, anchor="middle", weight=700)}
<rect x="{x + width - 70}" y="{y + 12}" width="58" height="25" rx="13" fill="{star_color(star)}"/>{text(x + width - 41, y + 29, number(star, 2) + "★", 10, fill="#101925" if star < 6.5 else "#ffd966", anchor="middle", weight=700)}
{mod_strip(entry['mods'], {}, x=x + 12, y=y + 103, icon_size=30, max_width=width - 24, preserve_artwork_ratio=True)}
<rect x="{x}" y="{y + visual_height + 10}" width="4" height="13" rx="2" fill="{CYAN if (index + 1) % 3 == 0 else PINK}"/>{fitted_text(x + 10, y + visual_height + 23, entry['title'], 15, width - 10, fill="#101824", weight=700)}
{fitted_text(x, y + visual_height + 47, entry['artist'], 10, width - 92, fill="#101824")}{text(x + width, y + visual_height + 47, number(entry['accuracy'], 2) + f"% · {entry['misses']}m", 9, fill="#e33c83", anchor="end", weight=700)}
<line x1="{x}" y1="{y + visual_height + 56}" x2="{x + width}" y2="{y + visual_height + 56}" stroke="#c8ced1" stroke-dasharray="2 3"/>
{fitted_text(x, y + visual_height + 74, combo, 9, width - 126, fill="#101824", weight=700)}{text(x + width, y + visual_height + 74, pp_change, 9, fill="#168f9b", anchor="end", weight=700)}</g>"""


def build_bp_fix_svg(payload: dict) -> tuple[str, int]:
    entries = payload["entries"]
    rows = (len(entries) + COLUMNS - 1) // COLUMNS
    height = CONTENT_TOP + rows * CARD_HEIGHT + max(0, rows - 1) * ROW_GAP + 32
    cards = "".join(_card(entry, index) for index, entry in enumerate(entries))
    profile_payload = {**payload, "section_title": "BP FIX"}
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<defs><linearGradient id="bp-fix-shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#07111d" stop-opacity="0"/><stop offset="1" stop-color="#07111d" stop-opacity=".92"/></linearGradient><pattern id="bp-fix-dots" width="17" height="17" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#26303a" opacity=".06"/></pattern></defs>
<rect width="{WIDTH}" height="{height}" fill="#f5f1e9"/><rect y="185" width="{WIDTH}" height="{height - 185}" fill="url(#bp-fix-dots)"/><rect width="420" height="4" fill="{PINK}"/><rect x="420" width="980" height="4" fill="{CYAN}"/>{bp_profile(profile_payload)}{_summary(payload)}{cards}</svg>"""
    return svg, height


async def render_bp_fix_svg(payload: dict) -> BytesIO:
    svg, height = build_bp_fix_svg(payload)
    return await render_svg_jpeg_async(svg, width=WIDTH, height=height, quality=90, image_rendering="optimize_speed")
