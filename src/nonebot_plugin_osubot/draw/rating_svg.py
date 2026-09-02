"""Native resvg renderer for multiplayer rating cards."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from io import BytesIO

from .svg_components import fitted_text, image, text
from .svg_render import render_svg_jpeg_async


WIDTH = 1280
MIN_HEIGHT = 900
PINK = "#ec3f83"
RED = "#ff708e"
BLUE = "#62cddd"
CYAN = "#61ced8"


def _short_score(value: object) -> str:
    score = float(value or 0)
    if score >= 1_000_000:
        return f"{score / 1_000_000:.2f}M"
    if score >= 1_000:
        return f"{score / 1_000:.1f}K"
    return f"{score:g}"


def _percent(value: object) -> str:
    return f"{float(value or 0):.1%}"


def _avatar(
    player: dict,
    x: float,
    y: float,
    size: float,
    clip_id: str,
    *,
    circular: bool = False,
    stroke: str | None = None,
    stroke_width: float = 0,
) -> str:
    source = player.get("avatar_data")
    if circular:
        shape = f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 2}"/>'
        background = f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 2}" fill="#26323d"/>'
        outline = (
            f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 2 - stroke_width / 2}" fill="none" stroke="{stroke}" stroke-width="{stroke_width}"/>'
            if stroke and stroke_width
            else ""
        )
    else:
        radius = min(7, size / 5)
        shape = f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{radius}"/>'
        background = f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{radius}" fill="#26323d"/>'
        outline = ""
    return (
        f'<defs><clipPath id="{clip_id}">{shape}</clipPath></defs>{background}'
        f"{image(source, x, y, size, size, clip=clip_id)}{outline}"
    )


def _player_identity(
    player: dict,
    x: float,
    row_y: float,
    max_name_width: float,
    clip_id: str,
    *,
    subtitle: str = "",
) -> str:
    name_y = row_y + (30 if subtitle else 42)
    parts = [
        _avatar(player, x, row_y + 13.5, 45, clip_id, circular=not subtitle),
        fitted_text(x + 57, name_y, player.get("name", "未知玩家"), 16, max_name_width, weight=700),
    ]
    if subtitle:
        parts.append(fitted_text(x + 57, row_y + 50, subtitle, 10, max_name_width, fill="#ffffff"))
    return "".join(parts)


def _team_side(side: str, name: str, players: list[dict], x: float, y: float, width: float) -> str:
    accent = RED if side == "red" else BLUE
    height = 43 + 72 * len(players)
    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="#0d1620" stroke="#ffffff" stroke-opacity=".08"/>',
        f'<line x1="{x}" y1="{y + 42}" x2="{x + width}" y2="{y + 42}" stroke="{accent}" stroke-width="2"/>',
        fitted_text(x + 15, y + 27, f"{name} · PLAYER RATING", 11, width - 30, fill=accent, weight=800),
    ]
    for index, player in enumerate(players):
        row_y = y + 43 + index * 72
        if index:
            parts.append(
                f'<line x1="{x}" y1="{row_y}" x2="{x + width}" y2="{row_y}" stroke="#ffffff" stroke-opacity=".05"/>'
            )
        parts.extend(
            [
                _player_identity(
                    player,
                    x + 13,
                    row_y,
                    width - 13 - 57 - 205,
                    f"rating-{side}-avatar-{index}",
                    subtitle=str(player.get("record_text") or ""),
                ),
                text(x + width - 182, row_y + 30, _short_score(player.get("total_score")), 16, weight=700),
                text(x + width - 182, row_y + 50, "总分", 10),
                text(
                    x + width - 30,
                    row_y + 44,
                    f"{float(player.get('rating') or 0):.2f}",
                    23,
                    fill=CYAN,
                    anchor="end",
                    weight=800,
                ),
            ]
        )
    return "".join(parts)


def _team_height(data: dict) -> int:
    largest_side = max(len(data.get("red_players") or []), len(data.get("blue_players") or []))
    return max(MIN_HEIGHT, 485 + 72 * largest_side)


def _team_svg(data: dict) -> tuple[str, int]:
    height = _team_height(data)
    red_players = list(data.get("red_players") or [])
    blue_players = list(data.get("blue_players") or [])
    red_name = str(data.get("red_name") or "红队")
    blue_name = str(data.get("blue_name") or "蓝队")
    mvp = data.get("mvp") or {}
    mvp_team_name = red_name if mvp.get("team") == "red" else blue_name
    side_y = 354
    side_width = 598.5
    parts = [
        '<defs><linearGradient id="rating-team-header" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#481e2d"/><stop offset=".498" stop-color="#481e2d"/><stop offset=".502" stop-color="#172e47"/><stop offset="1" stop-color="#172e47"/></linearGradient><linearGradient id="rating-mvp" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#3b2335"/><stop offset="1" stop-color="#142736"/></linearGradient></defs>',
        f'<rect width="{WIDTH}" height="{height}" fill="#101722"/>',
        '<rect width="1280" height="188" fill="url(#rating-team-header)"/>',
        text(44, 58, "RED SIDE", 12, fill=RED, weight=800),
        fitted_text(44, 113, red_name, 38, 430, weight=800),
        text(1236, 58, "BLUE SIDE", 12, fill=BLUE, anchor="end", weight=800),
        fitted_text(1236, 113, blue_name, 38, 430, anchor="end", weight=800),
        text(
            640,
            105,
            f"{int(data.get('red_wins') or 0)} : {int(data.get('blue_wins') or 0)}",
            54,
            anchor="middle",
            weight=800,
        ),
        text(640, 132, "FINAL SCORE", 11, anchor="middle"),
        '<rect x="34" y="210" width="1212" height="126" fill="url(#rating-mvp)" stroke="#f15a92" stroke-opacity=".24"/>',
        _avatar(mvp, 56, 229, 88, "rating-mvp-avatar", circular=True, stroke=PINK, stroke_width=4),
        text(179, 247, "MATCH MVP", 12, fill=PINK, weight=800),
        fitted_text(179, 284, mvp.get("name", "未知玩家"), 27, 520, weight=800),
        fitted_text(
            179,
            309,
            f"{mvp_team_name} · {int(mvp.get('wins') or 0)}W—{int(mvp.get('losses') or 0)}L",
            10,
            520,
        ),
    ]
    for center, label, value, color in (
        (849, "评分", f"{float(mvp.get('rating') or 0):.2f}", PINK),
        (999, "总分", _short_score(mvp.get("total_score")), "#ffffff"),
        (1149, "胜率", _percent(mvp.get("win_rate")), "#ffffff"),
    ):
        parts.append(text(center, 258, label, 11, anchor="middle", weight=700))
        parts.append(text(center, 291, value, 22, fill=color, anchor="middle", weight=800))
    parts.extend(
        [
            _team_side("red", red_name, red_players, 34, side_y, side_width),
            _team_side("blue", blue_name, blue_players, 647.5, side_y, side_width),
            fitted_text(34, height - 18, f"{data.get('title', '')} · MP {data.get('match_id', '')}", 10, 620),
            text(
                1246,
                height - 18,
                f"OSUBOT MULTIPLAYER RATING · {data.get('algorithm', '')}",
                10,
                anchor="end",
            ),
        ]
    )
    return "".join(parts), height


def _head_to_head_height(data: dict) -> int:
    return max(MIN_HEIGHT, 435 + 72 * len(data.get("players") or []))


def _head_to_head_svg(data: dict) -> tuple[str, int]:
    players = list(data.get("players") or [])
    height = _head_to_head_height(data)
    mvp = data.get("mvp") or {}
    table_x = 42
    table_y = 335
    table_width = 1196
    parts = [
        '<defs><radialGradient id="rating-h2h-glow" cx="82%" cy="0%" r="70%"><stop stop-color="#8b3167" stop-opacity=".4"/><stop offset="1" stop-color="#8b3167" stop-opacity="0"/></radialGradient><pattern id="rating-h2h-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#ffffff" stroke-opacity=".035"/></pattern><linearGradient id="rating-h2h-mvp" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#ec3f83" stop-opacity=".16"/><stop offset="1" stop-color="#ec3f83" stop-opacity="0"/></linearGradient></defs>',
        f'<rect width="{WIDTH}" height="{height}" fill="#081522"/>',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#rating-h2h-glow)"/>',
        f'<rect width="{WIDTH}" height="{height}" fill="url(#rating-h2h-grid)"/>',
        '<line y1="165" x2="1280" y2="165" stroke="#ffffff" stroke-opacity=".09"/>',
        text(42, 53, "HEAD-TO-HEAD PERFORMANCE INDEX", 12, fill=PINK, weight=800),
        fitted_text(42, 108, f"个人混战评分 / {data.get('title', '')}", 40, 850, weight=800),
        text(1238, 51, f"MP {data.get('match_id', '')}", 12, anchor="end"),
        text(
            1238,
            77,
            f"{int(data.get('game_count') or 0)} 局 · {int(data.get('player_count') or len(players))} 名选手 · HEAD TO HEAD",
            12,
            anchor="end",
        ),
        '<rect x="42" y="185" width="1196" height="130" fill="#0e1c29" fill-opacity=".87" stroke="#ffffff" stroke-opacity=".09"/>',
    ]
    kpis = (
        ("本场 MVP", mvp.get("name", "未知玩家"), PINK),
        ("最高 RATING", f"{float(mvp.get('rating') or 0):.2f}", "#ffffff"),
        ("最多 TOP 1", f"{int(data.get('max_top1_count') or 0)} 次", "#ffffff"),
        ("最高总分", _short_score(data.get("max_total_score")), "#ffffff"),
        ("平均评分", f"{float(data.get('average_rating') or 0):.2f}", "#ffffff"),
    )
    kpi_width = 1196 / 5
    for index, (label, value, color) in enumerate(kpis):
        left = 42 + index * kpi_width
        center = left + kpi_width / 2
        if index:
            parts.append(f'<line x1="{left}" y1="185" x2="{left}" y2="315" stroke="#ffffff" stroke-opacity=".09"/>')
        parts.append(text(center, 240, label, 11, anchor="middle", weight=700))
        parts.append(fitted_text(center, 279, value, 28, kpi_width - 24, fill=color, anchor="middle", weight=800))
    table_height = 42 + 72 * len(players)
    parts.extend(
        [
            f'<rect x="{table_x}" y="{table_y}" width="{table_width}" height="{table_height}" fill="#0b1925" fill-opacity=".92" stroke="#ffffff" stroke-opacity=".09"/>',
            f'<line x1="{table_x}" y1="{table_y + 42}" x2="{table_x + table_width}" y2="{table_y + 42}" stroke="#ffffff" stroke-opacity=".09"/>',
        ]
    )
    columns = (
        (59, "排名"),
        (121, "选手"),
        (726, "总分 / 均分"),
        (851, "TOP 1 / 出场"),
        (976, "TOP 1 率"),
        (1101, "评分"),
    )
    for x, label in columns:
        parts.append(text(x, table_y + 27, label, 11, weight=800))
    for index, player in enumerate(players):
        row_y = table_y + 42 + index * 72
        if index == 0:
            parts.extend(
                [
                    f'<rect x="{table_x}" y="{row_y}" width="{table_width}" height="72" fill="url(#rating-h2h-mvp)"/>',
                    f'<rect x="{table_x}" y="{row_y}" width="3" height="72" fill="{PINK}"/>',
                ]
            )
        if index:
            parts.append(
                f'<line x1="{table_x}" y1="{row_y}" x2="{table_x + table_width}" y2="{row_y}" stroke="#ffffff" stroke-opacity=".05"/>'
            )
        parts.extend(
            [
                text(59, row_y + 44, f"#{index + 1}", 21, weight=800),
                _player_identity(player, 121, row_y, 520, f"rating-h2h-avatar-{index}"),
                text(726, row_y + 31, _short_score(player.get("total_score")), 16, weight=700),
                text(726, row_y + 51, f"均分 {float(player.get('average_score') or 0):,.0f}", 10),
                text(
                    851,
                    row_y + 31,
                    f"{int(player.get('top1_count') or 0)} / {int(player.get('played') or 0)}",
                    16,
                    weight=700,
                ),
                text(851, row_y + 51, "第一名 / 出场", 10),
                text(976, row_y + 31, _percent(player.get("top1_rate")), 16, weight=700),
                text(976, row_y + 51, "TOP 1 RATE", 10),
                text(
                    1101,
                    row_y + 44,
                    f"{float(player.get('rating') or 0):.2f}",
                    24,
                    fill=CYAN,
                    weight=800,
                ),
            ]
        )
    parts.extend(
        [
            text(42, height - 18, f"OSUBOT HEAD-TO-HEAD ANALYTICS · {data.get('algorithm', '')}", 10),
            text(1238, height - 18, data.get("time_range", ""), 10, anchor="end"),
        ]
    )
    return "".join(parts), height


def build_rating_svg(data: dict) -> tuple[str, int]:
    body, height = _team_svg(data) if data.get("team_type") == "team-vs" else _head_to_head_svg(data)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">'
        f"{body}</svg>",
        height,
    )


async def render_rating_svg(data: dict) -> BytesIO:
    svg, height = build_rating_svg(data)
    return await render_svg_jpeg_async(
        svg,
        width=WIDTH,
        height=height,
        quality=92,
        image_rendering="optimize_speed",
    )
