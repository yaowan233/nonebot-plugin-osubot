"""Native SVG renderer for PP and global-rank history."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from io import BytesIO

from .svg_components import fitted_text, image, text
from .svg_render import render_svg_jpeg_async


WIDTH = 1280
HEIGHT = 760
PINK = "#e6377a"
TEAL = "#168b94"
INK = "#101824"
MUTED = "#727e87"
PLOT_LEFT = 128.0
PLOT_RIGHT = 1158.0
PLOT_TOP = 382.0
PLOT_BOTTOM = 642.0


def _number(value: object, digits: int = 0) -> str:
    return f"{float(value or 0):,.{digits}f}"


def _signed(value: object, suffix: str = "", digits: int = 0) -> str:
    number = float(value or 0)
    sign = "+" if number >= 0 else "−"
    return f"{sign}{_number(abs(number), digits)}{suffix}"


def _date_label(value: object) -> str:
    parts = str(value).split("-")
    return f"{parts[1]}.{parts[2]}" if len(parts) == 3 else str(value)


def _bounds(values: list[float]) -> tuple[float, float]:
    lower = min(values)
    upper = max(values)
    if lower == upper:
        padding = max(abs(lower) * 0.05, 1)
    else:
        padding = (upper - lower) * 0.08
    return lower - padding, upper + padding


def _x(index: int, count: int) -> float:
    if count <= 1:
        return (PLOT_LEFT + PLOT_RIGHT) / 2
    return PLOT_LEFT + index * (PLOT_RIGHT - PLOT_LEFT) / (count - 1)


def _y(value: float, lower: float, upper: float, *, inverse: bool = False) -> float:
    ratio = (value - lower) / max(upper - lower, 1e-9)
    if not inverse:
        ratio = 1 - ratio
    return PLOT_TOP + ratio * (PLOT_BOTTOM - PLOT_TOP)


def _points(
    values: list[float | int | None], lower: float, upper: float, *, inverse: bool = False
) -> list[tuple[float, float]]:
    count = len(values)
    return [
        (_x(index, count), _y(float(value), lower, upper, inverse=inverse))
        for index, value in enumerate(values)
        if value is not None
    ]


def _point_string(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _axis_labels(pp_bounds: tuple[float, float], rank_bounds: tuple[float, float]) -> str:
    parts: list[str] = []
    for index in range(5):
        ratio = index / 4
        y = PLOT_TOP + ratio * (PLOT_BOTTOM - PLOT_TOP)
        pp_value = pp_bounds[1] - ratio * (pp_bounds[1] - pp_bounds[0])
        rank_value = rank_bounds[0] + ratio * (rank_bounds[1] - rank_bounds[0])
        parts.extend(
            [
                f'<line x1="{PLOT_LEFT}" y1="{y:.2f}" x2="{PLOT_RIGHT}" y2="{y:.2f}" stroke="#d9dfe1" stroke-width="1"/>',
                text(PLOT_LEFT - 13, y + 4, _number(pp_value), 10, fill="#35434e", anchor="end"),
                text(PLOT_RIGHT + 13, y + 4, f"#{_number(rank_value)}", 10, fill="#35434e"),
            ]
        )
    return "".join(parts)


def _date_labels(dates: list[str]) -> str:
    if not dates:
        return ""
    label_count = min(6, len(dates))
    if label_count == 1:
        indices = [0]
    else:
        indices = sorted({round(index * (len(dates) - 1) / (label_count - 1)) for index in range(label_count)})
    return "".join(
        text(_x(index, len(dates)), 670, _date_label(dates[index]), 10, fill="#758089", anchor="middle")
        for index in indices
    )


def _chart(data: dict) -> str:
    dates = [str(value) for value in data.get("dates") or []]
    pp_values = [float(value) for value in data.get("pp_values") or []]
    rank_values = [value if value is None else int(value) for value in data.get("rank_display_values") or []]
    visible_ranks = [float(value) for value in rank_values if value is not None]
    pp_bounds = _bounds(pp_values)
    rank_bounds = _bounds(visible_ranks)
    pp_points = _points(pp_values, *pp_bounds)
    rank_points = _points(rank_values, *rank_bounds, inverse=True)
    pp_line = _point_string(pp_points)
    rank_line = _point_string(rank_points)
    area = ""
    if pp_points:
        area_path = " ".join(f"L{x:.2f},{y:.2f}" for x, y in pp_points)
        area = (
            f'<path d="M{pp_points[0][0]:.2f},{PLOT_BOTTOM:.2f} {area_path} '
            f'L{pp_points[-1][0]:.2f},{PLOT_BOTTOM:.2f} Z" fill="url(#history-pp-area)" clip-path="url(#history-plot-clip)"/>'
        )
    limited = bool(data.get("rank_window_limited"))
    rank_start_index = int(data.get("rank_start_index") or 0)
    rank_marker = ""
    if limited:
        marker_x = _x(rank_start_index, len(dates))
        rank_marker = (
            f'<line data-role="rank-window-start" x1="{marker_x:.2f}" y1="{PLOT_TOP}" x2="{marker_x:.2f}" y2="{PLOT_BOTTOM}" '
            'stroke="#168b94" stroke-opacity=".35" stroke-dasharray="4 5"/>'
        )
    parts = [
        '<rect x="44" y="318" width="1192" height="380" fill="#ffffff" stroke="#d3d8da"/>',
        text(64, 350, "PP 与全球排名变化", 12, fill=INK, weight=700),
        '<line x1="895" y1="345" x2="913" y2="345" stroke="#e6377a" stroke-width="3"/>',
        text(920, 349, "表现分数", 10, fill="#657078"),
        '<line x1="1033" y1="345" x2="1051" y2="345" stroke="#168b94" stroke-width="3"/>',
        text(1058, 349, "全球排名", 10, fill="#657078"),
        text(PLOT_LEFT, 373, "PP", 10, fill="#758089"),
        text(PLOT_RIGHT, 373, "全球排名", 10, fill="#758089", anchor="end"),
        _axis_labels(pp_bounds, rank_bounds),
        _date_labels(dates),
        area,
        rank_marker,
        f'<polyline data-role="pp-line" points="{pp_line}" fill="none" stroke="{PINK}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" clip-path="url(#history-plot-clip)"/>',
        f'<polyline data-role="rank-line" data-start-index="{rank_start_index}" points="{rank_line}" fill="none" stroke="{TEAL}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" clip-path="url(#history-plot-clip)"/>',
    ]
    if pp_points:
        parts.append(
            f'<circle cx="{pp_points[-1][0]:.2f}" cy="{pp_points[-1][1]:.2f}" r="5" fill="#fff" stroke="{PINK}" stroke-width="3"/>'
        )
    if rank_points:
        parts.append(
            f'<circle cx="{rank_points[-1][0]:.2f}" cy="{rank_points[-1][1]:.2f}" r="4" fill="#fff" stroke="{TEAL}" stroke-width="2.5"/>'
        )
    return "".join(parts)


def build_history_svg(data: dict) -> str:
    username = str(data.get("username") or "osu! 玩家")
    user_id = str(data.get("user_id") or "")
    rank_gain = float(data.get("rank_gain") or 0)
    rank_label = "窗口排名提升" if data.get("rank_window_limited") else "排名提升"
    parts = [
        '<defs><linearGradient id="history-profile" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#e8ece9"/><stop offset="1" stop-color="#f5f1e9"/></linearGradient><linearGradient id="history-pp-area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#e6377a" stop-opacity=".20"/><stop offset="1" stop-color="#e6377a" stop-opacity="0"/></linearGradient><clipPath id="history-avatar-clip"><rect x="42" y="55" width="88" height="88" rx="8"/></clipPath><clipPath id="history-plot-clip"><rect x="128" y="382" width="1030" height="260"/></clipPath></defs>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#f5f1e9"/>',
        '<rect width="384" height="5" fill="#e6377a"/><rect x="384" width="896" height="5" fill="#168b94"/>',
        '<rect y="5" width="390" height="195" fill="url(#history-profile)"/><line x1="390" y1="5" x2="390" y2="200" stroke="#cbd1d3"/><line x1="0" y1="200" x2="1280" y2="200" stroke="#cbd1d3"/>',
        '<rect x="51" y="64" width="88" height="88" rx="8" fill="#e6377a"/>',
        '<rect x="42" y="55" width="88" height="88" rx="8" fill="#ffffff"/>',
        text(86, 109, data.get("initial") or username[:1].upper(), 28, fill=INK, anchor="middle", weight=700),
        image(data.get("avatar_data"), 42, 55, 88, 88, clip="history-avatar-clip"),
        fitted_text(152, 89, username, 27, 205, fill=INK, weight=700),
        text(152, 111, f"UID {user_id}" if user_id else "osu! 玩家", 11, fill="#6f7b84"),
        '<rect x="152" y="123" width="118" height="25" fill="#ffffff" stroke="#c9ced1"/><rect x="152" y="123" width="4" height="25" fill="#168b94"/>',
        fitted_text(164, 140, data.get("mode") or "osu! 模式", 10, 96, fill="#26323c"),
        text(434, 46, "玩家成长档案", 11, fill=PINK, weight=700),
        fitted_text(434, 91, f"表现趋势 / 最近 {int(data.get('period_days') or 1)} 天", 38, 570, fill=INK, weight=700),
        text(1236, 49, f"记录区间 {data.get('period', '')}", 11, fill=MUTED, anchor="end"),
        text(434, 126, "起始 PP", 9, fill="#7d878e"),
        text(434, 151, _number(data.get("start_pp")), 16, fill=INK, weight=700),
        text(588, 126, "当前 PP", 9, fill="#7d878e"),
        text(588, 151, _number(data.get("current_pp")), 16, fill=INK, weight=700),
        text(742, 126, "最近 30 天", 9, fill="#7d878e"),
        text(742, 151, _signed(data.get("recent_pp_gain"), " pp"), 16, fill=PINK, weight=700),
        '<rect x="44" y="220" width="1192" height="82" fill="#ffffff" stroke="#d3d8da"/>',
    ]
    kpis = (
        ("PP 净增长", _signed(data.get("pp_gain")), PINK),
        ("当前全球排名", f"#{_number(data.get('current_rank'))}", INK),
        (rank_label, f"{'↑' if rank_gain >= 0 else '↓'}{_number(abs(rank_gain))}", TEAL),
        ("排名变化幅度", f"{_number(data.get('rank_gain_rate'), 1)}%", INK),
    )
    for index, (label, value, color) in enumerate(kpis):
        x = 44 + index * 298
        if index:
            parts.append(f'<line x1="{x}" y1="220" x2="{x}" y2="302" stroke="#d3d8da"/>')
        parts.extend(
            [
                text(x + 20, 247, label, 9, fill="#7c858b"),
                fitted_text(x + 20, 280, value, 23, 255, fill=color, weight=700),
            ]
        )
    parts.extend(
        [
            _chart(data),
            text(
                1236,
                734,
                f"nonebot_plugin_osubot · 历史趋势 · 数据来源：{data.get('source_label', '')}",
                9,
                fill="#929a9f",
                anchor="end",
            ),
        ]
    )
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">{"".join(parts)}</svg>'


async def render_history_svg(data: dict) -> BytesIO:
    return await render_svg_jpeg_async(build_history_svg(data), width=WIDTH, height=HEIGHT, quality=92)
