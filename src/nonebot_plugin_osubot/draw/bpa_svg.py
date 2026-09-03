"""Native SVG renderer for the best-performance analysis report."""

# The fixed-layout SVG is easier to audit when its markup stays on one line.
# ruff: noqa: E501

from __future__ import annotations

import datetime
import math
from collections import defaultdict
from collections.abc import Iterable
from io import BytesIO
from typing import Any

from .svg_components import fitted_text, image, text
from .svg_render import escape_text, render_svg_jpeg_async, text_width


WIDTH = 1620
HEIGHT = 1229
INK = "#1c1c22"
MUTED = "#8b8892"
GRID = "#eae7e0"
INDIGO = "#4f46e5"
ROSE = "#e11d48"
AMBER = "#d97706"
TEAL = "#0d9488"
VIOLET = "#7c3aed"
SKY = "#0284c7"
EMERALD = "#059669"
PINK = "#db2777"
GRADE_COLORS = {
    "XH": "#9edcec",
    "X": "#ffc83a",
    "SH": "#9edcec",
    "S": "#ffc83a",
    "A": "#84d61c",
    "B": "#e9b941",
    "C": "#fa8a59",
    "D": "#f55757",
}
GRADE_ORDER = ["XH", "X", "SH", "S", "A", "B", "C", "D"]


def _value(value: object, default: float = 0.0) -> float:
    try:
        result = float(value or 0)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _number(value: object, digits: int = 1) -> str:
    return f"{_value(value):,.{digits}f}"


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _duration(seconds: float) -> str:
    rounded = max(0, round(seconds))
    return f"{rounded // 60}:{rounded % 60:02d}"


def _nice_step(value: float) -> float:
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude
    if normalized <= 1.5:
        step = 1
    elif normalized <= 3:
        step = 2
    elif normalized <= 7:
        step = 5
    else:
        step = 10
    return step * magnitude


def _axis_scale(values: list[float], target_intervals: int = 5) -> tuple[float, float, list[float]]:
    minimum, maximum = min(values), max(values)
    if minimum == maximum:
        padding = max(abs(minimum) * 0.1, 1)
        minimum -= padding
        maximum += padding
    step = _nice_step((maximum - minimum) / target_intervals)
    lower = math.floor(minimum / step) * step
    upper = math.ceil(maximum / step) * step
    ticks = [lower + index * step for index in range(round((upper - lower) / step) + 1)]
    return lower, upper, ticks


def _count_scale(maximum: float, target_intervals: int = 4) -> tuple[float, list[float]]:
    step = _nice_step(maximum / target_intervals)
    upper = max(step, math.ceil(maximum / step) * step)
    ticks = [index * step for index in range(round(upper / step) + 1)]
    return upper, ticks


def _sample_indices(count: int, maximum: int) -> set[int]:
    if count <= maximum:
        return set(range(count))
    step = math.ceil(count / maximum)
    return set(range(0, count, step))


def _category_label(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value or "-")


def _polyline(points: Iterable[tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _card(x: float, y: float, width: float, height: float, number: str, title: str, color: str, hint: str = "") -> str:
    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" fill="#ffffff" stroke="#ddd9cf"/>',
        f'<rect x="{x + 16}" y="{y + 15}" width="18" height="18" rx="5" fill="{color}"/>',
        text(x + 25, y + 28, number, 10, anchor="middle", weight=600),
        text(x + 43, y + 29, title, 13, fill=INK, weight=600),
    ]
    if hint:
        parts.append(fitted_text(x + width - 16, y + 28, hint, 10, width * 0.45, fill=MUTED, anchor="end"))
    return "".join(parts)


def _empty(x: float, y: float, width: float, height: float) -> str:
    return text(x + width / 2, y + height / 2 + 4, "暂无数据", 11, fill=MUTED, anchor="middle")


def _header(data: dict[str, Any]) -> str:
    username = str(data.get("username") or data.get("name") or "osu! 玩家")
    avatar = data.get("avatar_data")
    user_id = str(data.get("user_id") or "")
    source = str(data.get("source_label") or "")
    mode = str(data.get("mode_label") or "osu! 模式")
    mode_icon = str(data.get("mode_icon") or "")
    stats = data.get("stats") or {}
    meta = " · ".join(
        value for value in (f"UID {user_id}" if user_id else "", source, "" if mode_icon else mode) if value
    )
    icon_x = min(149 + text_width(username, 30) + 12, 940)
    parts = [
        '<g data-role="bpa-header">',
        '<defs><clipPath id="bpa-avatar"><rect x="55" y="60" width="76" height="76" rx="12"/></clipPath></defs>',
        '<rect x="55" y="60" width="76" height="76" rx="12" fill="#e7e4dc"/>',
        text(93, 111, username[:1].upper(), 27, fill=INDIGO, anchor="middle", weight=600) if not avatar else "",
        image(str(avatar or ""), 55, 60, 76, 76, clip="bpa-avatar"),
        text(149, 70, "BEST PERFORMANCE ANALYSIS", 11, fill=INDIGO, weight=600),
        fitted_text(149, 115, username, 30, 770, fill=INK, weight=600),
        (
            f'<text data-role="bpa-mode-icon" data-font="extra" x="{icon_x:.2f}" y="115" '
            f'font-size="30" font-weight="400" text-anchor="start" fill="{INDIGO}">{escape_text(mode_icon)}</text>'
            if mode_icon
            else ""
        ),
        fitted_text(149, 137, meta, 11, 770, fill="#85828a"),
        text(1566, 72, "加权 PP", 10, fill="#85828a", anchor="end"),
        text(1566, 115, _number(stats.get("weighted_pp"), 1), 38, fill=INDIGO, anchor="end", weight=600),
        text(1566, 137, f"raw 合计  {_number(stats.get('total_pp'), 1)}", 12, fill="#85828a", anchor="end"),
        '<line x1="54" y1="164" x2="1566" y2="164" stroke="#1c1c22" stroke-width="2"/>',
        "</g>",
    ]
    return "".join(parts)


def _kpis(data: dict[str, Any]) -> str:
    stats = data.get("stats") or {}
    lengths = [
        _value(item.get("value")) if isinstance(item, dict) else _value(item) for item in data.get("length_ls") or []
    ]
    average_length = sum(lengths) / len(lengths) if lengths else 0
    values = [
        ("BP 数量", f"{int(_value(stats.get('bp_count')))}", "张", INK),
        ("平均准确率", _number(stats.get("avg_acc"), 2), "%", EMERALD),
        ("平均星数", _number(stats.get("avg_stars"), 2), "★", AMBER),
        ("平均 BPM", _number(stats.get("avg_bpm"), 1), "", PINK),
        ("平均时长", _duration(average_length), "", INDIGO),
        ("主力 Mod", _category_label(stats.get("top_mod")), "", INK),
    ]
    x, y, width, height = 54.0, 184.0, 1512.0, 72.0
    cell_width = width / len(values)
    parts = [
        '<g data-role="bpa-kpis">',
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" fill="#ffffff" stroke="#ddd9cf"/>',
    ]
    for index, (label, value, suffix, color) in enumerate(values):
        left = x + index * cell_width
        if index:
            parts.append(f'<line x1="{left}" y1="{y}" x2="{left}" y2="{y + height}" stroke="#eeeae1"/>')
        parts.extend(
            [
                text(left + 18, y + 26, label, 10, fill=MUTED),
                fitted_text(left + 18, y + 54, f"{value}{suffix}", 20, cell_width - 36, fill=color, weight=600),
            ]
        )
    parts.append("</g>")
    return "".join(parts)


def _star_points(data: dict[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for series in data.get("star_scatter") or []:
        if not isinstance(series, dict):
            continue
        for point in series.get("data") or []:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((_value(point[0]), _value(point[1])))
    return points


def _insights(data: dict[str, Any]) -> str:
    pp_values = [_value(value) for value in data.get("pp_ls") or []]
    weighted = [value * 0.95**index for index, value in enumerate(pp_values)]
    weighted_total = sum(weighted)
    top_ten = sum(weighted[:10])
    decay = 1 - pp_values[-1] / pp_values[0] if len(pp_values) > 1 and pp_values[0] else 0
    stars = [star for star, _pp in _star_points(data)]
    star_range = f"{min(stars):.1f}★ ~ {max(stars):.1f}★" if stars else "暂无"
    items = [
        (
            INDIGO,
            f"Top 10 占加权 PP  {_percent(top_ten / weighted_total if weighted_total else 0)}（{_number(round(top_ten), 0)} pp）",
        ),
        (ROSE, f"BP#1 → #{len(pp_values)} 单图 PP 衰减  {_percent(decay)}"),
        (AMBER, f"难度区间  {star_range}"),
    ]
    parts = ['<g data-role="bpa-insights">']
    cursor = 58.0
    widths = (275, 285, 260)
    for index, ((color, label), width) in enumerate(zip(items, widths)):
        if index:
            parts.append(f'<line x1="{cursor - 18}" y1="273" x2="{cursor - 18}" y2="289" stroke="#d8d4ca"/>')
        parts.extend(
            [
                f'<circle cx="{cursor}" cy="281" r="3" fill="{color}"/>',
                fitted_text(cursor + 12, 285, label, 12, width - 12, fill="#4a4855", weight=600),
            ]
        )
        cursor += width + 20
    parts.append("</g>")
    return "".join(parts)


def _curve(data: dict[str, Any]) -> str:
    x, y, width, height = 54.0, 306.0, 1004.0, 327.0
    parts = [
        '<g data-role="bpa-pp-curve">',
        _card(x, y, width, height, "01", "PP 价值曲线", INDIGO, "阴影为 Top 10 区间"),
    ]
    values = [_value(value) for value in data.get("pp_ls") or []]
    if not values:
        parts.extend([_empty(x, y + 40, width, height - 40), "</g>"])
        return "".join(parts)

    left, right, top, bottom = x + 62, x + width - 42, y + 68, y + height - 43
    lower, upper, ticks = _axis_scale(values)
    count = len(values)

    def px(index: int) -> float:
        return (left + right) / 2 if count <= 1 else left + index * (right - left) / (count - 1)

    def py(value: float) -> float:
        return bottom - (value - lower) / max(upper - lower, 1e-9) * (bottom - top)

    top_ten_end = px(min(9, count - 1))
    parts.append(
        f'<rect x="{left}" y="{top}" width="{max(0, top_ten_end - left):.2f}" height="{bottom - top}" fill="#4f46e5" opacity=".07"/>'
    )
    for tick in reversed(ticks):
        row_y = py(tick)
        parts.extend(
            [
                f'<line x1="{left}" y1="{row_y:.2f}" x2="{right}" y2="{row_y:.2f}" stroke="{GRID}"/>',
                text(left - 11, row_y + 4, _number(tick, 0), 10, fill=MUTED, anchor="end"),
            ]
        )
    points = [(px(index), py(value)) for index, value in enumerate(values)]
    point_string = _polyline(points)
    parts.extend(
        [
            f'<defs><linearGradient id="bpa-curve-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{INDIGO}" stop-opacity=".22"/><stop offset="1" stop-color="{INDIGO}" stop-opacity=".01"/></linearGradient></defs>',
            f'<path d="M{points[0][0]:.2f},{bottom:.2f} L{point_string.replace(" ", " L")} L{points[-1][0]:.2f},{bottom:.2f} Z" fill="url(#bpa-curve-area)"/>',
            f'<polyline points="{point_string}" fill="none" stroke="{INDIGO}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    )
    average = sum(values) / count
    average_y = py(average)
    parts.extend(
        [
            f'<line x1="{left}" y1="{average_y:.2f}" x2="{right}" y2="{average_y:.2f}" stroke="#b8b5bd" stroke-dasharray="5 4"/>',
            text(right + 8, average_y + 4, f"均 {_number(average, 1)}", 9, fill=MUTED),
        ]
    )
    label_indices = _sample_indices(count, 10)
    for index in sorted(label_indices):
        parts.append(text(px(index), bottom + 22, index + 1, 9, fill=MUTED, anchor="middle"))
    anchors = sorted({0, count // 4, count // 2, count - 1})
    for anchor_index, index in enumerate(anchors):
        point_x, point_y = points[index]
        parts.extend(
            [
                f'<circle cx="{point_x:.2f}" cy="{point_y:.2f}" r="4" fill="{INDIGO}" stroke="#fff" stroke-width="2"/>',
                text(
                    point_x + (10 if anchor_index == 0 else 0),
                    max(top + 12, point_y - 10),
                    f"#{index + 1} · {_number(values[index], 0)}",
                    10,
                    fill=INK,
                    anchor="start" if anchor_index == 0 else "middle",
                    weight=600,
                ),
            ]
        )
    weighted = [value * 0.95**index for index, value in enumerate(values)]
    share = sum(weighted[:10]) / sum(weighted) if sum(weighted) else 0
    parts.extend([text(left + 24, bottom - 14, f"Top 10 · {_percent(share)}", 10, fill=INDIGO, weight=600), "</g>"])
    return "".join(parts)


def _grade(data: dict[str, Any]) -> str:
    x, y, width, height = 1072.0, 306.0, 494.0, 327.0
    counts = dict.fromkeys(GRADE_ORDER, 0)
    for series in data.get("star_scatter") or []:
        if isinstance(series, dict) and str(series.get("name")) in counts:
            counts[str(series["name"])] = len(series.get("data") or [])
    total = sum(counts.values())
    s_count = sum(counts[grade] for grade in ("XH", "X", "SH", "S"))
    parts = [
        '<g data-role="bpa-grade">',
        _card(x, y, width, height, "02", "评级构成", ROSE, f"S/SS {_percent(s_count / total if total else 0)}"),
    ]
    bar_x, bar_y, bar_width, bar_height = x + 16, y + 55, width - 32, 26
    parts.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="7" fill="#f0ede5"/>')
    cursor = bar_x
    for grade in GRADE_ORDER:
        count = counts[grade]
        segment = bar_width * count / total if total else 0
        if segment > 0:
            parts.append(
                f'<rect x="{cursor:.2f}" y="{bar_y}" width="{segment:.2f}" height="{bar_height}" fill="{GRADE_COLORS[grade]}"/>'
            )
            cursor += segment
    row_y = y + 109
    for index, grade in enumerate(GRADE_ORDER):
        baseline = row_y + index * 26
        opacity = 1 if counts[grade] else 0.42
        parts.extend(
            [
                f'<line x1="{x + 16}" y1="{baseline - 14}" x2="{x + width - 16}" y2="{baseline - 14}" stroke="#f0ede5"/>',
                f'<rect x="{x + 17}" y="{baseline - 8}" width="9" height="9" rx="3" fill="{GRADE_COLORS[grade]}" opacity="{opacity}"/>',
                text(x + 35, baseline, grade, 12, fill=INK, weight=600, opacity=opacity),
                text(x + 123, baseline, f"{counts[grade]} 张", 12, fill="#4a4855", anchor="end", opacity=opacity),
                text(
                    x + width - 17,
                    baseline,
                    _percent(counts[grade] / total if total else 0),
                    12,
                    fill=MUTED,
                    anchor="end",
                    opacity=opacity,
                ),
            ]
        )
    parts.append("</g>")
    return "".join(parts)


def _star_efficiency(data: dict[str, Any]) -> str:
    x, y, width, height = 54.0, 647.0, 494.0, 286.0
    parts = ['<g data-role="bpa-star-efficiency">', _card(x, y, width, height, "03", "星数效率", AMBER, "0.5★ 分桶")]
    buckets: defaultdict[float, list[float]] = defaultdict(list)
    for star, pp in _star_points(data):
        buckets[math.floor(star * 2) / 2].append(pp)
    if not buckets:
        parts.extend([_empty(x, y + 38, width, height - 38), "</g>"])
        return "".join(parts)
    keys = sorted(buckets)
    counts = [len(buckets[key]) for key in keys]
    averages = [sum(buckets[key]) / len(buckets[key]) for key in keys]
    left, right, top, bottom = x + 60, x + width - 28, y + 76, y + height - 37
    count_max, count_ticks = _count_scale(max(counts))
    pp_low, pp_high, pp_ticks = _axis_scale(averages, 4)
    slot = (right - left) / len(keys)
    max_count_index = counts.index(max(counts))
    line_points: list[tuple[float, float]] = []
    for tick in count_ticks:
        row_y = bottom - tick / count_max * (bottom - top)
        parts.extend(
            [
                f'<line x1="{left}" y1="{row_y:.2f}" x2="{right}" y2="{row_y:.2f}" stroke="{GRID}"/>',
                text(left - 8, row_y + 4, _number(tick, 0), 9, fill=MUTED, anchor="end"),
            ]
        )
    for tick in pp_ticks:
        row_y = bottom - (tick - pp_low) / max(pp_high - pp_low, 1e-9) * (bottom - top)
        parts.append(text(right + 8, row_y + 4, _number(tick, 0), 9, fill=MUTED))
    for index, (key, count, average) in enumerate(zip(keys, counts, averages)):
        center = left + slot * (index + 0.5)
        bar_height = (bottom - top) * count / count_max
        color = AMBER if index == max_count_index else "#f2d5a7"
        parts.append(
            f'<rect x="{center - slot * 0.27:.2f}" y="{bottom - bar_height:.2f}" width="{slot * 0.54:.2f}" height="{bar_height:.2f}" rx="4" fill="{color}"/>'
        )
        if index in _sample_indices(len(keys), 8):
            parts.append(text(center, bottom + 20, f"{key:.1f}★", 9, fill=MUTED, anchor="middle"))
        ratio = (average - pp_low) / max(pp_high - pp_low, 1e-9)
        line_points.append((center, bottom - ratio * (bottom - top)))
    parts.append(
        f'<polyline points="{_polyline(line_points)}" fill="none" stroke="{INK}" stroke-width="2.5" stroke-linejoin="round"/>'
    )
    for point_x, point_y in line_points:
        parts.append(
            f'<circle cx="{point_x:.2f}" cy="{point_y:.2f}" r="3.5" fill="{INK}" stroke="#fff" stroke-width="1.5"/>'
        )
    max_pp_index = averages.index(max(averages))
    parts.extend(
        [
            text(left, y + 63, "数量", 9, fill=MUTED),
            text(right, y + 63, "平均 PP", 9, fill=MUTED, anchor="end"),
            text(
                line_points[max_pp_index][0],
                max(top + 10, line_points[max_pp_index][1] - 9),
                _number(averages[max_pp_index], 1),
                9,
                fill=INK,
                anchor="middle",
            ),
            "</g>",
        ]
    )
    return "".join(parts)


def _horizontal_bars(
    data: dict[str, Any],
    *,
    role: str,
    x: float,
    number: str,
    title: str,
    color: str,
    soft: str,
    key: str,
    percentage: bool,
    labels_left_aligned: bool = False,
    adaptive_bar_max_height: float | None = None,
) -> str:
    y, width, height = 647.0, 494.0, 286.0
    parts = [f'<g data-role="{role}">', _card(x, y, width, height, number, title, color)]
    rows = [
        row
        for row in data.get(key) or []
        if isinstance(row, dict) and math.floor(_value(row.get("value")) * 10 + 0.5) > 0
    ]
    rows = sorted(rows, key=lambda row: _value(row.get("value")), reverse=True)[:9]
    if not rows:
        parts.extend([_empty(x, y + 38, width, height - 38), "</g>"])
        return "".join(parts)
    total = sum(_value(row.get("value")) for row in rows)
    maximum = max(_value(row.get("value")) for row in rows)
    row_height = 204 / len(rows)
    bar_height = (
        min(adaptive_bar_max_height, max(16.0, row_height - 16.0)) if adaptive_bar_max_height is not None else 16.0
    )
    top = y + 67
    label_x = x + 24 if labels_left_aligned else x + 108
    bar_left = x + 68 if labels_left_aligned else x + 116
    bar_max_width = width - (178 if labels_left_aligned else 212)
    for index, row in enumerate(rows):
        baseline = top + index * row_height
        value = _value(row.get("value"))
        fill = color if index == 0 else soft
        bar_width = bar_max_width * value / maximum if maximum else 0
        label = f"{_number(value, 1)} · {_percent(value / total if total else 0)}" if percentage else _number(value, 1)
        parts.extend(
            [
                fitted_text(
                    label_x,
                    baseline + 4,
                    _category_label(row.get("name")),
                    11,
                    38 if labels_left_aligned else 90,
                    fill=INK,
                    anchor="start" if labels_left_aligned else "end",
                ),
                f'<rect x="{bar_left}" y="{baseline - bar_height / 2 - 1:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="4" fill="{fill}"/>',
                fitted_text(bar_left + bar_width + 7, baseline + 4, label, 10, 92, fill=MUTED),
            ]
        )
    parts.append("</g>")
    return "".join(parts)


def _quarter_histogram(dates: list[object]) -> tuple[list[str], list[int]]:
    buckets: defaultdict[int, int] = defaultdict(int)
    for raw in dates:
        value = str(raw)
        try:
            year = int(value[:4])
            month = int(value[5:7])
        except (TypeError, ValueError):
            continue
        if 1 <= month <= 12:
            quarter_index = year * 4 + (month - 1) // 3
            buckets[quarter_index] += 1
    if not buckets:
        return [], []
    quarter_indices = list(range(min(buckets), max(buckets) + 1))
    labels = [f"{index // 4}Q{index % 4 + 1}" for index in quarter_indices]
    return labels, [buckets[index] for index in quarter_indices]


def _acc_histogram(values: list[object]) -> tuple[list[str], list[int], int]:
    numbers = [_value(value) for value in values]
    if not numbers:
        return [], [], -1
    minimum = min(99.5, math.floor(min(numbers) * 2) / 2)
    bins = [round(minimum + index * 0.5, 1) for index in range(max(1, round((100 - minimum) / 0.5)))]
    counts = [0] * len(bins)
    for value in numbers:
        index = min(len(bins) - 1, max(0, math.floor((value - minimum) / 0.5 + 1e-6)))
        counts[index] += 1
    average = sum(numbers) / len(numbers)
    highlight = min(len(bins) - 1, max(0, math.floor((average - minimum) / 0.5 + 1e-6)))
    return [f"{value:.1f}%" for value in bins], counts, highlight


def _bpm_histogram(values: list[object]) -> tuple[list[str], list[int], int, str]:
    numbers = [_value(value) for value in values if _value(value) > 0]
    if not numbers:
        return [], [], -1, "10 BPM 分桶"
    minimum = math.floor(min(numbers) / 10) * 10
    maximum = math.floor(max(numbers) / 10) * 10
    bins = list(range(minimum, maximum + 1, 10))
    counts = [0] * len(bins)
    for value in numbers:
        index = min(len(bins) - 1, max(0, math.floor((value - minimum) / 10)))
        counts[index] += 1
    peak = counts.index(max(counts))
    return [str(value) for value in bins], counts, peak, f"峰值 {bins[peak]}–{bins[peak] + 9} BPM · {counts[peak]} 张"


def _mini_histogram(
    *,
    role: str,
    x: float,
    number: str,
    title: str,
    color: str,
    soft: str,
    hint: str,
    labels: list[str],
    counts: list[int],
    highlight: int,
) -> str:
    y, width, height = 947.0, 494.0, 216.0
    parts = [f'<g data-role="{role}">', _card(x, y, width, height, number, title, color, hint)]
    if not labels:
        parts.extend([_empty(x, y + 38, width, height - 38), "</g>"])
        return "".join(parts)
    left, right, top, bottom = x + 48, x + width - 18, y + 61, y + height - 40
    maximum, ticks = _count_scale(max(counts))
    slot = (right - left) / len(labels)
    for tick in reversed(ticks):
        row_y = bottom - tick / maximum * (bottom - top)
        parts.extend(
            [
                f'<line x1="{left}" y1="{row_y:.2f}" x2="{right}" y2="{row_y:.2f}" stroke="{GRID}"/>',
                text(left - 9, row_y + 4, _number(tick, 0), 9, fill=MUTED, anchor="end"),
            ]
        )
    label_indices = _sample_indices(len(labels), 10)
    for index, (label, count) in enumerate(zip(labels, counts)):
        center = left + slot * (index + 0.5)
        bar_height = (bottom - top) * count / maximum
        fill = color if index == highlight else soft
        bar_width = max(3, slot * 0.58)
        parts.append(
            f'<rect x="{center - bar_width / 2:.2f}" y="{bottom - bar_height:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="3" fill="{fill}"/>'
        )
        if index in label_indices:
            parts.append(fitted_text(center, bottom + 19, label, 9, max(34, slot * 1.7), fill=MUTED, anchor="middle"))
    parts.append("</g>")
    return "".join(parts)


def build_bpa_svg(data: dict[str, Any]) -> str:
    """Build the complete fixed-layout BPA report as SVG markup."""
    dates = list(data.get("date_ls") or [])
    time_labels, time_counts = _quarter_histogram(dates)
    time_highlight = time_counts.index(max(time_counts)) if time_counts else -1
    acc_labels, acc_counts, acc_highlight = _acc_histogram(list(data.get("acc_ls") or []))
    bpm_labels, bpm_counts, bpm_highlight, bpm_hint = _bpm_histogram(list(data.get("bpm_ls") or []))
    generated_on = str(data.get("generated_on") or datetime.date.today().isoformat())
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<rect width="{WIDTH}" height="{HEIGHT}" fill="#e9e6df"/>
<rect x="24" y="24" width="1572" height="1181" rx="18" fill="#f5f3ee" stroke="#ddd9cf"/>
{_header(data)}{_kpis(data)}{_insights(data)}{_curve(data)}{_grade(data)}{_star_efficiency(data)}
{_horizontal_bars(data, role="bpa-mod-contribution", x=562, number="04", title="Mod 贡献", color=TEAL, soft="#a7dcd7", key="mod_pp_ls", percentage=True, labels_left_aligned=True, adaptive_bar_max_height=32)}
{_horizontal_bars(data, role="bpa-mapper-preference", x=1072, number="05", title="Mapper 偏好", color=VIOLET, soft="#d3c3f0", key="mapper_pp_ls", percentage=False)}
{_mini_histogram(role="bpa-time-distribution", x=54, number="06", title="BP 时间分布", color=SKY, soft="#b3d9ef", hint="按季度统计", labels=time_labels, counts=time_counts, highlight=time_highlight)}
{_mini_histogram(role="bpa-acc-distribution", x=562, number="07", title="ACC 分布", color=EMERALD, soft="#a9dcc7", hint="0.5% 分桶", labels=acc_labels, counts=acc_counts, highlight=acc_highlight)}
{_mini_histogram(role="bpa-bpm-distribution", x=1072, number="08", title="BPM 分布", color=PINK, soft="#f0b8d2", hint=bpm_hint, labels=bpm_labels, counts=bpm_counts, highlight=bpm_highlight)}
{text(56, 1192, "OSUBOT · BP ANALYSIS", 10, fill="#a3a0a8")}{text(1564, 1192, generated_on, 10, fill="#a3a0a8", anchor="end")}
</svg>"""


async def render_bpa_svg(data: dict[str, Any]) -> BytesIO:
    """Rasterize the native BPA report without launching a browser."""
    return await render_svg_jpeg_async(build_bpa_svg(data), width=WIDTH, height=HEIGHT, quality=92)
