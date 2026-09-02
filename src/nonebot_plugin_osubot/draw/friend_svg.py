"""好友列表面板原生 SVG 渲染（resvg）。

版式以 friend_templates/index.html 为视觉基准；国家旗帜 emoji 在无系统字体的
原生渲染中不可达，统一降级为两位国家代码文本。文字最终由 svg_render 用项目
缓存字体绘制，坐标必须使用绝对值。
"""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from .svg_components import fitted_text, image, supporter_badge, text
from .svg_render import render_svg_jpeg_async, text_width, truncate_text

WIDTH = 1280
COLUMNS = 5
GRID_GAP = 14
GRID_MARGIN_X = 40
GRID_TOP = 22
CARD_HEIGHT = 160
HEADER_HEIGHT = 124
FOOTER_GAP = 26
FOOTER_HEIGHT = 44

BG = "#101722"
CARD_BG = "#0b1925"
PINK = "#ec3f83"
CYAN = "#62cddd"
GREEN = "#4ade80"
MUTED = "#82929d"
DIM = "#718794"
FOOT = "#586b78"

CARD_WIDTH = (WIDTH - GRID_MARGIN_X * 2 - GRID_GAP * (COLUMNS - 1)) / COLUMNS
_EDGE = WIDTH - 48  # 头部内容右缘


def _header(payload: dict) -> str:
    me_size = 72
    me_x = 48
    me_y = (HEADER_HEIGHT - me_size) / 2
    me_cx = me_x + me_size / 2
    me_cy = HEADER_HEIGHT / 2
    title_x = me_x + me_size + 18

    total = payload.get("total", 0)
    mutual_count = payload.get("mutual_count", 0)
    online_count = payload.get("online_count", 0)
    sort_text = f"排序：{payload.get('sort_label') or '默认'} · OSU! FRIENDS"
    range_text = f"{payload.get('start', 1)}-{payload.get('end', 0)}"
    total_text = f" / {total}"
    meta_width = max(text_width(sort_text, 12), text_width(range_text, 16) + text_width(total_text, 12))
    title = truncate_text(f"{payload.get('me_name', '')} 的好友", max(0, _EDGE - title_x - meta_width - 24), 29)

    sub_total = f"共 {total} 位好友"
    sub_mutual = f"互关 {mutual_count}"
    sub_online = f"在线 {online_count}"
    sub_x = title_x
    subs = [text(sub_x, 82, sub_total, 12, fill=MUTED)]
    sub_x += text_width(sub_total, 12) + 12
    subs.append(text(sub_x, 82, sub_mutual, 12, fill="#ff8ab0"))
    sub_x += text_width(sub_mutual, 12) + 12
    subs.append(text(sub_x, 82, sub_online, 12, fill=GREEN))

    return f"""<rect width="{WIDTH}" height="{HEADER_HEIGHT}" fill="url(#friend-head-shade)"/><defs><clipPath id="friend-me-clip"><circle cx="{me_cx}" cy="{me_cy}" r="{me_size / 2}"/></clipPath></defs>
{image(payload.get("me_avatar"), me_x, me_y, me_size, me_size, clip="friend-me-clip")}<circle cx="{me_cx}" cy="{me_cy}" r="{me_size / 2}" fill="none" stroke="{PINK}" stroke-width="3"/>
{text(title_x, 63, title, 29, weight=700)}{"".join(subs)}
{text(_EDGE - text_width(total_text, 12), 50, range_text, 16, fill=CYAN, anchor="end", weight=700)}{text(_EDGE, 50, total_text, 12, fill=MUTED, anchor="end")}
{text(_EDGE, 73, sort_text, 12, fill=MUTED, anchor="end")}
<line x1="0" y1="{HEADER_HEIGHT - 0.5}" x2="{WIDTH}" y2="{HEADER_HEIGHT - 0.5}" stroke="#ffffff" stroke-opacity=".07"/>"""


def _badges(friend: dict, cx: float, y: float) -> str:
    items = []
    if friend.get("mutual"):
        items.append("mutual")
    if friend.get("supporter"):
        items.append("supporter")
    if not items:
        return ""
    widths = {"mutual": text_width("互关", 9) + 12, "supporter": 15 * 0.72 + 15 * 0.35}
    total_width = sum(widths[item] for item in items) + 4 * (len(items) - 1)
    cursor = cx - total_width / 2
    parts = []
    for item in items:
        width = widths[item]
        if item == "mutual":
            parts.append(
                f'<rect x="{cursor}" y="{y}" width="{width}" height="15" rx="3" fill="{PINK}" fill-opacity=".15" stroke="{PINK}" stroke-opacity=".25"/>'
                + text(cursor + width / 2, y + 11, "互关", 9, fill="#ff8ab0", anchor="middle", weight=700)
            )
        else:
            parts.append(supporter_badge(cursor, y, 1, height=15))
        cursor += width + 4
    return "".join(parts)


def _card(friend: dict, index: int) -> str:
    row, column = divmod(index, COLUMNS)
    x = GRID_MARGIN_X + column * (CARD_WIDTH + GRID_GAP)
    y = HEADER_HEIGHT + GRID_TOP + row * (CARD_HEIGHT + GRID_GAP)
    cx = x + CARD_WIDTH / 2
    mutual = bool(friend.get("mutual"))
    online = bool(friend.get("online"))

    clip_id = f"friend-av-{index}"
    avatar = 62
    avatar_x = cx - avatar / 2
    avatar_y = y + 18
    ring = PINK if mutual else "#26323d"

    if mutual:
        frame = f'<rect x="{x}" y="{y}" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="10" fill="{CARD_BG}" stroke="{PINK}" stroke-opacity=".25"/><rect x="{x}" y="{y}" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="10" fill="url(#friend-mutual-shade)"/>'
    else:
        frame = f'<rect x="{x}" y="{y}" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="10" fill="{CARD_BG}" stroke="#ffffff" stroke-opacity=".07"/>'

    dot = ""
    if online:
        dot_cx = avatar_x + 55.5
        dot_cy = avatar_y + 53.5
        dot = f'<circle cx="{dot_cx}" cy="{dot_cy}" r="9.5" fill="{GREEN}" opacity=".3"/><circle cx="{dot_cx}" cy="{dot_cy}" r="6.5" fill="{GREEN}" stroke="{CARD_BG}" stroke-width="3"/>'

    country = (friend.get("country") or "").upper()
    sub = f"{country} uid {friend['uid']}" if country else f"uid {friend['uid']}"
    name_fill = "#ffffff" if online else "#b8c4ce"

    return f"""<g data-role="friend-card">{frame}
<defs><clipPath id="{clip_id}"><circle cx="{cx}" cy="{avatar_y + avatar / 2}" r="{avatar / 2}"/></clipPath></defs>
{image(friend.get("avatar"), avatar_x, avatar_y, avatar, avatar, clip=clip_id)}<circle cx="{cx}" cy="{avatar_y + avatar / 2}" r="{avatar / 2}" fill="none" stroke="{ring}" stroke-width="2"/>{dot}
{fitted_text(cx, y + 102, friend.get("name", ""), 14, CARD_WIDTH - 16, anchor="middle", fill=name_fill, weight=700)}
{text(cx, y + 118, sub, 11, fill=DIM, anchor="middle")}
{_badges(friend, cx, y + 127)}</g>"""


def build_friend_svg(payload: dict) -> tuple[str, int]:
    friends = payload.get("friends") or []
    rows = (len(friends) + COLUMNS - 1) // COLUMNS
    grid_height = rows * CARD_HEIGHT + max(0, rows - 1) * GRID_GAP
    footer_y = HEADER_HEIGHT + GRID_TOP + grid_height + FOOTER_GAP
    height = footer_y + FOOTER_HEIGHT
    cards = "".join(_card(friend, index) for index, friend in enumerate(friends))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<defs><linearGradient id="friend-head-shade" x1="0" y1="0" x2="1" y2="0.35"><stop offset="0" stop-color="#1a2c3e"/><stop offset="0.7" stop-color="{BG}"/></linearGradient><linearGradient id="friend-mutual-shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PINK}" stop-opacity=".1"/><stop offset="1" stop-color="{PINK}" stop-opacity="0"/></linearGradient></defs>
<rect width="{WIDTH}" height="{height}" fill="{BG}"/>{_header(payload)}{cards}
<line x1="{GRID_MARGIN_X}" y1="{footer_y}" x2="{WIDTH - GRID_MARGIN_X}" y2="{footer_y}" stroke="#ffffff" stroke-opacity=".07"/>
{text(GRID_MARGIN_X, footer_y + 23, "OSUBOT FRIENDS · /FRIEND", 10, fill=FOOT, weight=700)}{text(WIDTH - GRID_MARGIN_X, footer_y + 23, f"{payload.get('me_name', '')} · 好友列表", 10, fill=FOOT, anchor="end", weight=700)}
</svg>"""
    return svg, height


async def render_friend_svg(payload: dict) -> bytes:
    svg, height = build_friend_svg(payload)
    result = await render_svg_jpeg_async(svg, width=WIDTH, height=height, quality=92)
    return result.getvalue()
