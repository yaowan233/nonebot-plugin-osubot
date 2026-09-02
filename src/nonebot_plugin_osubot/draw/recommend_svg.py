"""推荐谱面面板原生 SVG 渲染（resvg）。

版式为 design/recommend 概念 B（osubot 暗色家族）；文字由 svg_render 用项目
缓存字体绘制，坐标必须使用绝对值。星数色阶复用 svg_components.star_color。
"""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from .svg_components import fitted_text, image, star_color, text
from .svg_render import render_svg_jpeg_async, text_width, truncate_text

WIDTH = 1080
HEADER_HEIGHT = 108
SECTION_TOP = 20
SECTION_MARGIN_X = 40
COLUMN_GAP = 20
COLUMN_WIDTH = (WIDTH - SECTION_MARGIN_X * 2 - COLUMN_GAP) / 2
SECTION_HEAD_HEIGHT = 25
SECTION_GAP = 16
CARD_HEIGHT = 72
CARD_GAP = 9
COVER_WIDTH = 96
FOOTER_MARGIN = 18
FOOTER_HEIGHT = 35

BG = "#101722"
CARD_BG = "#0b1925"
COVER_BG = "#0a111c"
PINK = "#ec3f83"
CYAN = "#62cddd"
MUTED = "#82929d"
DIM = "#586b78"
MAPID = "#b8c8d4"
PP = "#ffc94d"
ACC = "#4ade80"

SECTION_ACCENTS = {
    "overall": PINK,
    "easy": "#4fc0ff",
    "medium": "#7cff4f",
    "hard": "#ff8068",
}


def _star_text(bg: str) -> str:
    red, green, blue = (int(bg[index : index + 2], 16) for index in (1, 3, 5))
    return "#171a21" if (0.299 * red + 0.587 * green + 0.114 * blue) / 255 > 0.6 else "#ffffff"


def _chip(
    x: float, y: float, label: str, fill: str, text_fill: str, *, stroke: str | None = None, fill_opacity: float = 1
) -> str:
    width = text_width(label, 10) + 12
    stroke_attr = f' stroke="{stroke}" stroke-opacity=".25"' if stroke else ""
    opacity_attr = f' fill-opacity="{fill_opacity}"' if fill_opacity < 1 else ""
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="14" rx="5" fill="{fill}"{opacity_attr}{stroke_attr}/>'
        + text(x + width / 2, y + 11, label, 10, fill=text_fill, anchor="middle", weight=700)
    )


def _chip_width(label: str) -> float:
    return text_width(label, 10) + 12


def _header(payload: dict) -> str:
    me_size = 64
    me_x = SECTION_MARGIN_X
    me_y = (HEADER_HEIGHT - me_size) / 2
    me_cx = me_x + me_size / 2
    me_cy = HEADER_HEIGHT / 2
    title_x = me_x + me_size + 16

    mode = (payload.get("mode") or "osu").upper()
    mode_suffix = " 模式"
    section_titles = payload.get("section_titles") or []
    sections_line = " / ".join(section_titles)
    meta_width = max(
        text_width(mode, 15) + text_width(mode_suffix, 12),
        text_width(sections_line, 12),
    )
    title = truncate_text(
        f"{payload.get('username', '')} 的推荐谱面",
        max(0, WIDTH - SECTION_MARGIN_X - title_x - meta_width - 20),
        26,
    )

    total = payload.get("total_count", 0)
    sub_parts = []
    sub_x = title_x
    sub_parts.append(text(sub_x, 74, "共 ", 12, fill=MUTED))
    sub_x += text_width("共 ", 12)
    sub_parts.append(text(sub_x, 74, str(total), 12, fill=CYAN, weight=700))
    sub_x += text_width(str(total), 12)
    rest = " 张推荐谱面"
    if payload.get("player_id"):
        rest += f" · player #{payload['player_id']}"
    sub_parts.append(text(sub_x, 74, rest, 12, fill=MUTED))

    right = WIDTH - SECTION_MARGIN_X
    return f"""<rect width="{WIDTH}" height="{HEADER_HEIGHT}" fill="url(#rec-head-shade)"/><defs><clipPath id="rec-me-clip"><circle cx="{me_cx}" cy="{me_cy}" r="{me_size / 2}"/></clipPath></defs>
{image(payload.get("avatar"), me_x, me_y, me_size, me_size, clip="rec-me-clip")}<circle cx="{me_cx}" cy="{me_cy}" r="{me_size / 2}" fill="none" stroke="{PINK}" stroke-width="3"/>
{text(title_x, 52, title, 26, weight=700)}{"".join(sub_parts)}
{text(right - text_width(mode_suffix, 12), 46, mode, 15, fill=CYAN, anchor="end", weight=700)}{text(right, 46, mode_suffix, 12, fill=MUTED, anchor="end")}
{text(right, 67, sections_line, 12, fill=MUTED, anchor="end")}
<line x1="0" y1="{HEADER_HEIGHT - 0.5}" x2="{WIDTH}" y2="{HEADER_HEIGHT - 0.5}" stroke="#ffffff" stroke-opacity=".07"/>"""


def _card(item: dict, rank: int, x: float, y: float, key: str) -> str:
    clip_id = f"rec-cover-{key}"
    parts = [
        f'<rect x="{x}" y="{y}" width="{COLUMN_WIDTH}" height="{CARD_HEIGHT}" rx="10" fill="{CARD_BG}" stroke="#ffffff" stroke-opacity=".07"/>',
        f'<defs><clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{COLUMN_WIDTH}" height="{CARD_HEIGHT}" rx="10"/></clipPath></defs>',
    ]
    cover = item.get("cover")
    if cover:
        parts.append(image(cover, x, y, COVER_WIDTH, CARD_HEIGHT, clip=clip_id))
    else:
        parts.append(
            f'<rect x="{x}" y="{y}" width="{COVER_WIDTH}" height="{CARD_HEIGHT}" fill="{COVER_BG}" clip-path="url(#{clip_id})"/>'
        )

    label = f"#{rank}"
    badge_width = text_width(label, 10) + 12
    badge_y = y + CARD_HEIGHT - 21
    parts.append(
        f'<rect x="{x + 5}" y="{badge_y}" width="{badge_width}" height="16" rx="5" fill="#000000" fill-opacity=".72"/>'
    )
    parts.append(text(x + 5 + badge_width / 2, badge_y + 12, label, 10, fill=CYAN, anchor="middle", weight=700))

    info_x = x + COVER_WIDTH + 12
    parts.append(
        fitted_text(info_x, y + 29, item.get("title", ""), 13, COLUMN_WIDTH - COVER_WIDTH - 12 - 92, weight=700)
    )

    tag_y = y + 39
    tag_x = info_x
    stars = float(item.get("stars") or 0)
    star_fill = star_color(stars)
    star_label = f"★ {stars:.2f}"
    parts.append(_chip(tag_x, tag_y, star_label, star_fill, _star_text(star_fill)))
    tag_x += _chip_width(star_label) + 5
    map_label = f"#{item.get('map_id', 0)}"
    parts.append(_chip(tag_x, tag_y, map_label, "#ffffff", MAPID, fill_opacity=0.10))
    tag_x += _chip_width(map_label) + 5
    # NM（无 mod）不占用标签位；有 mod 时用实心粉 chip 强化识别
    mod = (item.get("mod_str") or "NM").upper()
    if mod != "NM":
        parts.append(_chip(tag_x, tag_y, mod, PINK, "#ffffff"))

    right = x + COLUMN_WIDTH - 14
    pp = str(round(float(item.get("pred_pp") or 0)))
    parts.append(text(right - text_width("pp", 11), y + 36, pp, 19, fill=PP, anchor="end", weight=700))
    parts.append(text(right, y + 36, "pp", 11, fill=PP, anchor="end", weight=700))
    parts.append(
        text(right, y + 49, f"{float(item.get('pred_acc') or 0):.2f}%", 11, fill=ACC, anchor="end", weight=700)
    )
    return f'<g data-role="recommend-card">{"".join(parts)}</g>'


def _section_head(title: str, count: int, x: float, y: float, accent: str) -> str:
    return (
        f'<rect x="{x}" y="{y + 1}" width="4" height="13" rx="2" fill="{accent}"/>'
        + text(x + 12, y + 13, title, 15, weight=700)
        + text(x + COLUMN_WIDTH, y + 12, f"{count} MAPS", 10, fill=DIM, anchor="end", weight=700)
    )


def _sections_height(groups: list[tuple[str, list]]) -> float:
    height = 0.0
    for index, (_key, items) in enumerate(groups):
        height += SECTION_HEAD_HEIGHT + len(items) * CARD_HEIGHT + max(0, len(items) - 1) * CARD_GAP
        if index < len(groups) - 1:
            height += SECTION_GAP
    return height


def _cards_column(items: list, x: float, y: float, key_prefix: str, start_rank: int = 1) -> str:
    return "".join(
        _card(item, start_rank + index, x, y + index * (CARD_HEIGHT + CARD_GAP), f"{key_prefix}-{index}")
        for index, item in enumerate(items)
    )


def build_recommend_svg(payload: dict) -> tuple[str, int]:
    overall = payload.get("overall")
    side = payload.get("side") or []
    flat = payload.get("flat") or []
    left_x = SECTION_MARGIN_X
    right_x = SECTION_MARGIN_X + COLUMN_WIDTH + COLUMN_GAP
    body_top = HEADER_HEIGHT + SECTION_TOP
    body = []

    if overall is not None:
        main_items = overall["items"]
        body.append(_section_head(overall["title"], len(main_items), left_x, body_top, SECTION_ACCENTS["overall"]))
        body.append(_cards_column(main_items, left_x, body_top + SECTION_HEAD_HEIGHT, "overall"))
        main_height = _sections_height([("overall", main_items)])
        side_height = 0.0
        side_y = body_top
        for index, section in enumerate(side):
            items = section["items"]
            accent = SECTION_ACCENTS.get(section.get("key"), PINK)
            body.append(_section_head(section["title"], len(items), right_x, side_y, accent))
            body.append(_cards_column(items, right_x, side_y + SECTION_HEAD_HEIGHT, f"side-{index}"))
            side_height += SECTION_HEAD_HEIGHT + len(items) * CARD_HEIGHT + max(0, len(items) - 1) * CARD_GAP
            if index < len(side) - 1:
                side_height += SECTION_GAP
            side_y = body_top + side_height + (SECTION_GAP if index < len(side) - 1 else 0)
        sections_height = max(main_height, side_height)
    else:
        # 无综合分组（旧版 API）：两列均分平铺，排名为全局序号
        half = (len(flat) + 1) // 2
        left_items, right_items = flat[:half], flat[half:]
        body.append(_cards_column(left_items, left_x, body_top, "flat-l"))
        body.append(_cards_column(right_items, right_x, body_top, "flat-r", start_rank=half + 1))
        left_height = len(left_items) * CARD_HEIGHT + max(0, len(left_items) - 1) * CARD_GAP
        right_height = len(right_items) * CARD_HEIGHT + max(0, len(right_items) - 1) * CARD_GAP
        sections_height = max(left_height, right_height)

    footer_y = HEADER_HEIGHT + SECTION_TOP + sections_height + FOOTER_MARGIN
    height = round(footer_y + FOOTER_HEIGHT)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<defs><linearGradient id="rec-head-shade" x1="0" y1="0" x2="1" y2="0.35"><stop offset="0" stop-color="#1a2c3e"/><stop offset="0.7" stop-color="{BG}"/></linearGradient></defs>
<rect width="{WIDTH}" height="{height}" fill="{BG}"/>{_header(payload)}{"".join(body)}
<line x1="{SECTION_MARGIN_X}" y1="{footer_y}" x2="{WIDTH - SECTION_MARGIN_X}" y2="{footer_y}" stroke="#ffffff" stroke-opacity=".07"/>
{text(SECTION_MARGIN_X, footer_y + 21, "OSUBOT RECOMMEND · /推荐", 10, fill=DIM, weight=700)}{text(WIDTH - SECTION_MARGIN_X, footer_y + 21, "POWERED BY OSU RECOMMENDER", 10, fill=DIM, anchor="end", weight=700)}
</svg>"""
    return svg, height


async def render_recommend_svg(payload: dict) -> bytes:
    svg, height = build_recommend_svg(payload)
    result = await render_svg_jpeg_async(svg, width=WIDTH, height=height, quality=92)
    return result.getvalue()
