"""Native SVG renderer for BP and other multi-score card lists."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from .svg_components import fitted_text, image, mod_strip, number, star_color, supporter_badge, text
from .svg_render import render_svg_jpeg_async, text_width


WIDTH = 1400
HEADER_HEIGHT = 185
CONTENT_TOP = 213
PINK = "#ff3f8e"
CYAN = "#20a9b8"


def _profile(payload: dict) -> str:
    user = payload["user"]
    stats = user.get("statistics") or {}
    team = user.get("team") or {}
    support = min(5, max(0, int(user.get("support_level") or 0)))
    name = str(user.get("name") or "")
    badge_width = 17 + support * 8 if support else 0
    name_size = 34
    name_available = 205 - badge_width
    while name_size > 20 and text_width(name, name_size) > name_available:
        name_size -= 1
    name_width = min(text_width(name, name_size), name_available)
    team_uri = team.get("flag_data")
    team_image = image(team_uri, 182, 116, 31, 22, contain=True) if team_uri else ""
    meta_x = 220 if team_uri else 182
    first_line = user.get("country") or "--"
    if team:
        first_line += f" · {team.get('short_name') or team.get('name') or ''}"
    return f"""
<rect x="0" y="0" width="420" height="185" fill="#edf0ed"/>
<rect x="0" y="0" width="420" height="4" fill="{PINK}"/>
<rect x="416" y="24" width="4" height="67" fill="{PINK}"/>
<rect x="416" y="65" width="4" height="26" fill="{CYAN}"/>
<defs><clipPath id="bp-avatar"><rect x="48" y="34" width="110" height="110" rx="8"/></clipPath></defs>
<rect x="58" y="44" width="110" height="110" rx="8" fill="{PINK}"/>
{image(user.get("avatar_data"), 48, 34, 110, 110, clip="bp-avatar")}
{text(182, 57, f"OSU! {payload['section_title']}档案", 11, fill="#df347c", weight=700)}
{fitted_text(182, 96, name, name_size, name_available, fill="#101824", weight=700)}
{supporter_badge(182 + name_width + 8, 72, support)}
{team_image}
{fitted_text(meta_x, 130, first_line, 11, 385 - meta_x, fill="#101824", weight=700)}
{fitted_text(182, 151, f"全球 #{number(stats.get('global_rank'))} · {number(stats.get('pp'), 1)} pp", 11, 200, fill="#101824", weight=700)}
"""


def _summary(payload: dict) -> str:
    plays = payload["plays"]
    average_pp = sum(float(play["pp"]) for play in plays) / len(plays) if plays else 0
    average_accuracy = sum(float(play["accuracy"]) for play in plays) / len(plays) if plays else 0
    peak = max((float(play["stars"]) for play in plays), default=0)
    return f"""
<rect x="420" y="0" width="980" height="185" fill="#f5f1e9"/>
<rect x="420" y="0" width="980" height="4" fill="{CYAN}"/>
{text(485, 58, f"{payload['mode']}模式 / {payload['section_title']}", 11, fill="#101824", weight=700)}
{text(1352, 58, f"共 {len(plays)} 项 · {payload['generated_at']}", 11, fill="#101824", anchor="end")}
<line x1="485" y1="74" x2="1352" y2="74" stroke="#c9ced1"/>
{fitted_text(485, 126, payload["section_title"], 36, 430, fill="#101824", weight=700)}
{fitted_text(700, 126, f"/ {payload['range_label']}", 34, 330, fill=PINK, weight=700)}
{_fact(1060, "平均 PP", number(average_pp, 2))}
{_fact(1170, "平均准确率", number(average_accuracy, 2) + "%")}
{_fact(1290, "最高星数", number(peak, 2) + "★")}
"""


def _fact(x: float, label: str, value: str) -> str:
    return f'<line x1="{x}" y1="103" x2="{x}" y2="146" stroke="#c9ced1"/>{text(x + 12, 114, label, 9, fill="#168f9b", weight=700)}{text(x + 12, 139, value, 15, fill="#101824", weight=700)}'


def _card(play: dict, index: int, *, dense: bool) -> str:
    columns = 6 if dense else 5
    gap = 12 if dense else 15
    left = 30 if dense else 36
    width = (WIDTH - left * 2 - gap * (columns - 1)) / columns
    card_height = 177 if dense else 222
    visual_height = 112 if dense else 145
    row, column = divmod(index, columns)
    x = left + column * (width + gap)
    y = CONTENT_TOP + row * (card_height + (17 if dense else 24))
    title_size = 12 if dense else 15
    meta_size = 8 if dense else 10
    badge_size = 8 if dense else 10
    padding = 8 if dense else 12
    star = float(play["stars"])
    version_width = width - 118
    client = str(play.get("score_version") or "")
    client_text = "Lazer" if client == "lazer" else "Stable"
    clip_id = f"bp-cover-{index}"
    return f"""
<defs><clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{width}" height="{visual_height}" rx="8"/></clipPath></defs>
<rect x="{x}" y="{y}" width="{width}" height="{visual_height}" rx="8" fill="#101925" stroke="#ffffff"/>
{image(play.get("cover_data"), x, y, width, visual_height, clip=clip_id)}
<rect x="{x}" y="{y + visual_height * 0.35}" width="{width}" height="{visual_height * 0.65}" rx="8" fill="url(#bp-shade)" clip-path="url(#{clip_id})"/>
<rect x="{x + padding}" y="{y + padding}" width="{35 if not dense else 30}" height="{25 if not dense else 21}" rx="13" fill="{PINK}"/>
{text(x + padding + (17.5 if not dense else 15), y + padding + (17 if not dense else 15), f"#{play['index']}", badge_size, anchor="middle", weight=700)}
<rect x="{x + width - padding - (58 if not dense else 52)}" y="{y + padding}" width="{58 if not dense else 52}" height="{25 if not dense else 21}" rx="13" fill="{star_color(star)}"/>
{text(x + width - padding - (29 if not dense else 26), y + padding + (17 if not dense else 15), number(star, 2) + "★", badge_size, fill="#101925" if star < 6.5 else "#ffd966", anchor="middle", weight=700)}
{mod_strip(play["mods"], play.get("speed_changes") or {}, x=x + padding, y=y + visual_height - padding - (24 if dense else 30), icon_size=24 if dense else 30, max_width=width - 92, preserve_artwork_ratio=True)}
<rect x="{x + width - padding - (69 if dense else 82)}" y="{y + visual_height - padding - (23 if dense else 27)}" width="{69 if dense else 82}" height="{23 if dense else 27}" rx="14" fill="#f2c967"/>
{text(x + width - padding - (34.5 if dense else 41), y + visual_height - padding - (8 if dense else 9), number(play["pp"], 2) + " pp", 9 if dense else 11, fill="#17202b", anchor="middle", weight=700)}
<rect x="{x}" y="{y + visual_height + 10}" width="4" height="{10 if dense else 13}" rx="2" fill="{CYAN if (index + 1) % 3 == 0 else PINK}"/>
{fitted_text(x + 10, y + visual_height + (20 if dense else 23), play["title"], title_size, width - 10, fill="#101824", weight=700)}
{fitted_text(x, y + visual_height + (39 if dense else 47), play["artist"], meta_size, width - 70, fill="#101824")}
{text(x + width, y + visual_height + (39 if dense else 47), number(play["accuracy"], 2) + "%", meta_size, fill="#e33c83", anchor="end", weight=700)}
<line x1="{x}" y1="{y + visual_height + (47 if dense else 56)}" x2="{x + width}" y2="{y + visual_height + (47 if dense else 56)}" stroke="#c8ced1" stroke-dasharray="2 3"/>
{fitted_text(x, y + visual_height + (62 if dense else 74), play["version"], meta_size, version_width, fill="#101824")}
{text(x + width - 65, y + visual_height + (62 if dense else 74), client_text if client else "", meta_size - 1, fill="#168f9b" if client == "lazer" else "#101824", anchor="end", weight=700)}
{text(x + width, y + visual_height + (62 if dense else 74), play["date"], meta_size, fill=CYAN, anchor="end", weight=700)}
"""


def build_bp_svg(payload: dict) -> tuple[str, int]:
    plays = payload["plays"]
    dense = len(plays) > 50
    columns = 6 if dense else 5
    card_height = 177 if dense else 222
    row_gap = 17 if dense else 24
    rows = (len(plays) + columns - 1) // columns
    height = CONTENT_TOP + rows * card_height + max(0, rows - 1) * row_gap + 32
    cards = "".join(_card(play, index, dense=dense) for index, play in enumerate(plays))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<defs><linearGradient id="bp-shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#07111d" stop-opacity="0"/><stop offset="1" stop-color="#07111d" stop-opacity=".9"/></linearGradient><pattern id="bp-dots" width="17" height="17" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#26303a" opacity=".06"/></pattern></defs>
<rect width="{WIDTH}" height="{height}" fill="#f5f1e9"/>
<rect y="185" width="{WIDTH}" height="{height - 185}" fill="url(#bp-dots)"/>
<rect width="420" height="4" fill="{PINK}"/><rect x="420" width="980" height="4" fill="{CYAN}"/>
{_profile(payload)}{_summary(payload)}{cards}</svg>"""
    return svg, height


async def render_bp_svg(payload: dict) -> object:
    svg, height = build_bp_svg(payload)
    return await render_svg_jpeg_async(
        svg,
        width=WIDTH,
        height=height,
        quality=90,
        image_rendering="optimize_speed",
    )
