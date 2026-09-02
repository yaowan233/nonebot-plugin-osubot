"""Native resvg renderer for the group PP leaderboard."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from io import BytesIO

from .svg_components import fitted_text, image, text
from .svg_render import render_svg_jpeg_async, text_width, truncate_text


WIDTH = 1280
HEADER_HEIGHT = 118
PODIUM_HEIGHT = 330
BOTTOM_PADDING = 56
PINK = "#ec3f83"
CYAN = "#19a4ae"
BG = "#091522"


def _format_global_rank(value: object) -> str:
    try:
        rank = int(value or 0)
    except (TypeError, ValueError):
        rank = 0
    return f"#{rank:,}" if rank > 0 else "—"


def _format_delta(value: object, *, with_suffix: bool) -> str:
    if value is None:
        return "—" if with_suffix else "暂无历史变化"
    delta = float(value)
    if delta == 0:
        return "—" if with_suffix else "较上次无变化"
    sign = "+" if delta > 0 else ""
    formatted = f"{sign}{delta:,.1f}"
    return f"{formatted} pp" if with_suffix else f"较上次 {formatted}"


def _avatar(
    player: dict,
    x: float,
    y: float,
    size: float,
    clip_id: str,
    *,
    stroke: str,
    stroke_width: int,
) -> str:
    cx = x + size / 2
    cy = y + size / 2
    return f"""<defs><clipPath id="{clip_id}"><circle cx="{cx}" cy="{cy}" r="{size / 2}"/></clipPath></defs>
<circle cx="{cx}" cy="{cy}" r="{size / 2}" fill="#25313c"/>{image(player.get("avatar_data"), x, y, size, size, clip=clip_id)}
<circle cx="{cx}" cy="{cy}" r="{size / 2 - stroke_width / 2}" fill="none" stroke="{stroke}" stroke-width="{stroke_width}"/>"""


def _centered_name(player: dict, cx: float, y: float, max_width: float, size: int) -> str:
    name = str(player.get("osu_name") or "未知玩家")
    if not player.get("is_self"):
        return fitted_text(cx, y, name, size, max_width, anchor="middle", weight=700)
    tag_width = 22
    gap = 7
    name = truncate_text(name, max_width - tag_width - gap, size)
    name_width = text_width(name, size)
    left = cx - (name_width + gap + tag_width) / 2
    tag_x = left + name_width + gap
    return (
        text(left, y, name, size, weight=700)
        + f'<rect x="{tag_x}" y="{y - 13}" width="{tag_width}" height="14" rx="7" fill="{PINK}"/>'
        + text(tag_x + tag_width / 2, y - 3, "你", 8, anchor="middle", weight=700)
    )


def _podium_card(player: dict, x: float, bottom: float, index: int) -> str:
    place = int(player.get("place") or 0)
    first = place == 1
    width = 330 if first else 285
    height = 276 if first else 226
    y = bottom - height
    avatar_size = 98 if first else 82
    avatar_x = x + (width - avatar_size) / 2
    avatar_y = y + 25
    accent = PINK if first else CYAN
    medal = "#ffd26a" if first else "#ffffff"
    name_y = avatar_y + avatar_size + 29
    pp_y = name_y + 35
    summary_y = pp_y + 25
    pp_text = f"{float(player.get('pp') or 0):,.1f}"
    global_text = f"全球 {_format_global_rank(player.get('global_rank'))}"
    summary = f"{global_text} · {_format_delta(player.get('delta'), with_suffix=False)}"
    frame = (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="13" fill="url(#rank-first-card)" stroke="#ff5b9b" stroke-opacity=".33"/>'
        if first
        else f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="13" fill="#122333" stroke="#ffffff" stroke-opacity=".09"/>'
    )
    return f"""<g data-role="rank-podium">{frame}<rect x="{x}" y="{bottom - 5}" width="{width}" height="5" fill="{accent}"/>
{text(x + 17, y + 41, place, 30, fill=medal, weight=800)}
{_avatar(player, avatar_x, avatar_y, avatar_size, f"rank-podium-avatar-{index}", stroke=accent, stroke_width=4)}
{_centered_name(player, x + width / 2, name_y, width - 36, 18)}
{text(x + width / 2 - 8, pp_y, pp_text, 24, anchor="middle", weight=800)}
{text(x + width / 2 + text_width(pp_text, 24) / 2 + 3, pp_y, "pp", 10)}
{fitted_text(x + width / 2, summary_y, summary, 10, width - 24, anchor="middle")}</g>"""


def _podiums(payload: dict) -> str:
    podium = list(payload.get("podium") or [])
    widths = [330 if player.get("place") == 1 else 285 for player in podium]
    total_width = sum(widths) + max(0, len(widths) - 1) * 18
    cursor = (WIDTH - total_width) / 2
    parts = []
    for index, (player, width) in enumerate(zip(podium, widths)):
        parts.append(_podium_card(player, cursor, HEADER_HEIGHT + PODIUM_HEIGHT, index))
        cursor += width + 18
    return "".join(parts)


def _row_name(player: dict, x: float, row_y: float, max_width: float) -> str:
    qq_name = str(player.get("qq_name") or "")
    osu_name = str(player.get("osu_name") or "未知玩家")
    show_qq = bool(qq_name and qq_name != osu_name)
    name_y = row_y + (18 if show_qq else 28)
    tag_width = 22 if player.get("is_self") else 0
    gap = 7 if tag_width else 0
    name = truncate_text(osu_name, max_width - tag_width - gap, 14)
    parts = [text(x, name_y, name, 14, weight=700)]
    if tag_width:
        tag_x = x + text_width(name, 14) + gap
        parts.extend(
            [
                f'<rect x="{tag_x}" y="{name_y - 12}" width="{tag_width}" height="13" rx="6.5" fill="{PINK}"/>',
                text(tag_x + tag_width / 2, name_y - 3, "你", 8, anchor="middle", weight=700),
            ]
        )
    if show_qq:
        parts.append(fitted_text(x, row_y + 33, qq_name, 9, max_width))
    return "".join(parts)


def _rank_row(player: dict, y: float, index: int, *, pinned: bool = False) -> str:
    role = "pinned-row" if pinned else "rank-row"
    self_background = (
        f'<rect x="42" y="{y}" width="1196" height="45" fill="url(#rank-self-row)"/><rect x="42" y="{y}" width="3" height="45" fill="{PINK}"/>'
        if player.get("is_self")
        else ""
    )
    delta = player.get("delta")
    delta_fill = CYAN if delta not in (None, 0) else "#71818c"
    return f"""<g data-role="{role}">{self_background}
{text(59, y + 29, f"#{int(player.get('place') or 0)}", 16, weight=800)}
{_avatar(player, 125, y + 7, 31, f"rank-row-avatar-{index}", stroke="#25313c", stroke_width=1)}
{_row_name(player, 168, y, 610)}
{text(806, y + 20, f"{float(player.get('pp') or 0):,.1f} pp", 14, weight=700)}{text(806, y + 35, "总表现分", 9)}
{text(956, y + 20, _format_global_rank(player.get("global_rank")), 14, weight=700)}{text(956, y + 35, "全球", 9)}
{text(1101, y + 28, _format_delta(delta, with_suffix=True), 11, fill=delta_fill)}
<line x1="42" y1="{y + 45}" x2="1238" y2="{y + 45}" stroke="#ffffff" stroke-opacity=".055"/></g>"""


def _list(payload: dict, y: float) -> tuple[str, int]:
    rows = list(payload.get("rows") or [])
    pinned = payload.get("pinned")
    height = 32 + 45 * len(rows) + (79 if pinned else 0)
    parts = [
        f'<rect x="42" y="{y}" width="1196" height="{height}" fill="#0d1a26" fill-opacity=".87" stroke="#ffffff" stroke-opacity=".09"/>',
        f'<line x1="42" y1="{y + 32}" x2="1238" y2="{y + 32}" stroke="#ffffff" stroke-opacity=".09"/>',
    ]
    for x, label in ((59, "名次"), (125, "玩家"), (806, "表现分"), (956, "全球排名"), (1101, "PP 变化")):
        parts.append(text(x, y + 21, label, 9, weight=800))
    row_y = y + 32
    for index, player in enumerate(rows):
        parts.append(_rank_row(player, row_y, index))
        row_y += 45
    if pinned:
        gap_y = row_y
        gap_text = f"已省略第 {int(payload.get('hidden_start') or 21)}—{int(payload.get('hidden_end') or 20)} 名"
        gap_width = text_width(gap_text, 9)
        center = WIDTH / 2
        offsets = (
            -gap_width / 2 - 34,
            -gap_width / 2 - 22,
            -gap_width / 2 - 10,
            gap_width / 2 + 10,
            gap_width / 2 + 22,
            gap_width / 2 + 34,
        )
        for offset in offsets:
            parts.append(f'<circle cx="{center + offset}" cy="{gap_y + 17}" r="2" fill="#536674"/>')
        parts.append(text(center, gap_y + 21, gap_text, 9, anchor="middle"))
        parts.append(
            f'<line x1="42" y1="{gap_y + 34}" x2="1238" y2="{gap_y + 34}" stroke="#ffffff" stroke-opacity=".055"/>'
        )
        parts.append(_rank_row(pinned, gap_y + 34, len(rows), pinned=True))
    return "".join(parts), height


def _height(payload: dict) -> int:
    if not payload.get("visible"):
        return 490
    rows = len(payload.get("rows") or [])
    pinned = bool(payload.get("pinned"))
    list_height = 0 if not rows and not pinned else 18 + 32 + 45 * rows + (79 if pinned else 0)
    return HEADER_HEIGHT + PODIUM_HEIGHT + list_height + BOTTOM_PADDING


def build_rank_svg(payload: dict) -> tuple[str, int]:
    height = _height(payload)
    visible = list(payload.get("visible") or [])
    total = int(payload.get("total_count") or 0)
    meta = f"参榜 {total} 人"
    if total > 20:
        meta += " · 展示前 20"
    parts = [
        f'<rect width="{WIDTH}" height="{height}" fill="{BG}"/>',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#rank-glow-pink)"/>',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#rank-glow-cyan)"/>',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#rank-grid)"/>',
        text(42, 43, "GROUP PERFORMANCE LEADERBOARD", 11, fill=PINK, weight=800),
        fitted_text(42, 84, f"群内 PP 排名 · {payload.get('mode_name', '')}", 32, 760, weight=800),
        text(1238, 43, meta, 11, anchor="end"),
        text(1238, 67, f"更新于 {payload.get('updated_at', '')}", 11, anchor="end"),
        '<line y1="118" x2="1280" y2="118" stroke="#ffffff" stroke-opacity=".09"/>',
    ]
    if visible:
        parts.append(_podiums(payload))
        if payload.get("rows") or payload.get("pinned"):
            list_svg, _ = _list(payload, HEADER_HEIGHT + PODIUM_HEIGHT + 18)
            parts.append(list_svg)
    else:
        parts.extend(
            [
                '<rect x="42" y="198" width="1196" height="156" fill="#0d1a26" fill-opacity=".75" stroke="#ffffff" stroke-opacity=".09"/>',
                text(640, 282, "今天还没有可以进入榜单的玩家数据", 16, anchor="middle"),
            ]
        )
    pinned = payload.get("pinned")
    footer_left = "OSUBOT GROUP RANKING · TOP 20 + YOU" if pinned else "OSUBOT GROUP RANKING"
    footer_right = (
        f"你当前位于群内第 {int(pinned.get('place') or 0)} 名" if pinned else "仅统计当前模式 PP ≥ 100 的已绑定玩家"
    )
    parts.extend(
        [
            text(42, height - 18, footer_left, 9),
            text(1238, height - 18, footer_right, 9, anchor="end"),
        ]
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<defs><radialGradient id="rank-glow-pink" cx="80%" cy="5%" r="55%"><stop stop-color="#8c356a" stop-opacity=".27"/><stop offset="1" stop-color="#8c356a" stop-opacity="0"/></radialGradient><radialGradient id="rank-glow-cyan" cx="12%" cy="35%" r="50%"><stop stop-color="#167d8c" stop-opacity=".2"/><stop offset="1" stop-color="#167d8c" stop-opacity="0"/></radialGradient><pattern id="rank-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#ffffff" stroke-opacity=".035"/></pattern><linearGradient id="rank-first-card" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#32243b"/><stop offset="1" stop-color="#152938"/></linearGradient><linearGradient id="rank-self-row" x1="0" y1="0" x2="1" y2="0"><stop stop-color="{PINK}" stop-opacity=".17"/><stop offset="1" stop-color="{PINK}" stop-opacity="0"/></linearGradient></defs>{"".join(parts)}</svg>"""
    return svg, height


async def render_rank_svg(payload: dict) -> BytesIO:
    svg, height = build_rank_svg(payload)
    return await render_svg_jpeg_async(
        svg,
        width=WIDTH,
        height=height,
        quality=92,
        image_rendering="optimize_speed",
    )
