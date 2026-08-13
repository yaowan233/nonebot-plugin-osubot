"""Native SVG renderer for the full player information card."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from datetime import datetime

from .svg_components import (
    gradient_text,
    fitted_text,
    image,
    mod_strip,
    number,
    rank_seal,
    star_color,
    supporter_badge,
    text,
)
from .svg_render import render_svg_jpeg_async, text_width, truncate_text


WIDTH = 1740
HEIGHT = 1140
SIDE = 575
PINK = "#ff3f8e"
CYAN = "#20a9b8"
RANK_TIERS = {
    "iron": ("#bab3ab", "#bab3ab"),
    "bronze": ("#b88f7a", "#855c47"),
    "silver": ("#e0e0eb", "#a3a3c2"),
    "gold": ("#f0e4a8", "#e0c952"),
    "platinum": ("#a8f0ef", "#52e0df"),
    "rhodium": ("#d9f8d3", "#a0cf96"),
    "radiant": ("#97dcff", "#ed82ff"),
    "lustrous": ("#ffe600", "#ed82ff"),
    "base": ("#cccccc", "#999999"),
}


def _compact(value: object) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return "0"
    for divisor, suffix in ((1_000_000_000, "b"), (1_000_000, "m"), (1_000, "k")):
        if abs(amount) >= divisor:
            shown = amount / divisor
            digits = 0 if shown >= 100 else 1 if shown >= 10 else 2
            return f"{shown:.{digits}f}".rstrip("0").rstrip(".") + suffix
    return number(amount)


def _change(value: str | None) -> str:
    return f"  {value}" if value else ""


def _account_days(join_date: object) -> float | None:
    if not join_date:
        return None
    try:
        joined = datetime.fromisoformat(str(join_date).replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.now(joined.tzinfo) if joined.tzinfo else datetime.now()
    return max(1.0, (now - joined).total_seconds() / 86400)


def _account_age(days: float | None) -> str:
    if days is None:
        return "暂无数据"
    return f"{days / 365.2425:.1f} 年" if days >= 365 else f"{int(days)} 天"


def _average_play_time(seconds: object, count: object) -> str:
    average = int(float(seconds or 0) / max(1, int(count or 0)) + 0.5)
    return f"{average // 60}分{average % 60}秒" if average >= 60 else f"{average} 秒"


def _rank_colors(stats: dict) -> tuple[str, str]:
    rank = stats.get("global_rank")
    percent = stats.get("global_rank_percent")
    if rank is None or percent is None:
        return RANK_TIERS["base"]
    if int(rank) <= 100:
        return RANK_TIERS["lustrous"]
    percent = float(percent)
    tier = (
        "radiant"
        if percent < 0.0005
        else "rhodium"
        if percent < 0.0025
        else "platinum"
        if percent < 0.005
        else "gold"
        if percent < 0.025
        else "silver"
        if percent < 0.05
        else "bronze"
        if percent < 0.25
        else "iron"
        if percent < 0.5
        else "base"
    )
    return RANK_TIERS[tier]


def _left(user: dict) -> str:
    stats = user.get("statistics") or {}
    grades = stats.get("grade_counts") or {}
    support = min(5, max(0, int(user.get("support_level") or 0)))
    username = str(user.get("username") or "")
    name_size = 58
    badge_width = 19 + support * 8 if support else 0
    while name_size > 34 and text_width(username, name_size) > 410 - badge_width:
        name_size -= 1
    name_width = min(text_width(username, name_size), 410 - badge_width)
    team = user.get("team") or {}
    team_icon = image(team.get("flag_data"), 54, 485, 44, 30, contain=True) if team.get("flag_data") else ""
    team_x = 108 if team_icon else 54
    level = stats.get("level") or {}
    account_days = _account_days(user.get("join_date"))
    level_text = number(level.get("current"))
    progress_x = max(135, 54 + text_width(level_text, 58) + 20)
    progress_width = 464 - progress_x
    grade_values = (
        ("XH", grades.get("ssh")),
        ("X", grades.get("ss")),
        ("SH", grades.get("sh")),
        ("S", grades.get("s")),
        ("A", grades.get("a")),
    )
    grade_parts = []
    grade_width = 82
    for index, (rank, value) in enumerate(grade_values):
        x = 54 + index * grade_width
        grade_parts.append(rank_seal(rank, x + 11, 861))
        grade_parts.append(text(x + grade_width / 2, 914, number(value), 13, anchor="middle", weight=700))
        if index < 4:
            boundary = x + grade_width
            grade_parts.append(f'<line x1="{boundary}" y1="862" x2="{boundary}" y2="909" stroke="#ffffff12"/>')
    joined = str(user.get("join_date") or "")[:10] or "暂无数据"
    return f"""
<defs><clipPath id="info-side"><polygon points="0,0 {SIDE},0 500,{HEIGHT} 0,{HEIGHT}"/></clipPath></defs><g clip-path="url(#info-side)"><rect width="{SIDE}" height="{HEIGHT}" fill="#0b1420"/>
{image(user.get("background_data"), 0, 0, SIDE, HEIGHT) if user.get("background_data") else ""}<rect width="{SIDE}" height="{HEIGHT}" fill="#0b1420" opacity="{0.9 if user.get("background_data") else 0}"/>
{text(54, 66, f"OSU! 玩家档案 / {user.get('mode', '').upper()}模式", 14, fill="#ff67aa", weight=700)}
<defs><clipPath id="info-avatar"><rect x="54" y="100" width="246" height="246"/></clipPath></defs><rect x="68" y="114" width="246" height="246" fill="{PINK}"/>{image(user.get("avatar_data"), 54, 100, 246, 246, clip="info-avatar")}
{text(54, 392, f"{user.get('country_code', '--')} · 地区 #{number(stats.get('country_rank'))}", 13, fill="#ffffff", weight=700)}
{fitted_text(54, 458, username, name_size, 410 - badge_width, weight=700)}{supporter_badge(54 + name_width + 12, 421, support, height=28)}
{team_icon}{fitted_text(team_x, 506, (f"{team.get('short_name') or team.get('name')} · " if team else "") + f"UID {user['id']}", 14, 410 - (team_x - 54), fill="#ffffff", weight=700)}
<line x1="54" y1="540" x2="464" y2="540" stroke="#ffffff24"/>
{_identity_row(565, "注册时间", joined)}{_identity_row(607, "关注者", number(user.get("follower_count")))}{_identity_row(649, "徽章 / 成就", f"{len(user.get('badges') or [])} / {number(user.get('achievement_count'))}")}{_identity_row(691, "回放观看", number(stats.get("replays_watched_by_others")))}
{text(54, 785, level_text, 58, weight=700)}{text(progress_x, 758, "等级进度", 11, fill="#ffffff", weight=700)}{text(464, 758, number(level.get("progress")) + "%", 11, fill="#ffffff", anchor="end", weight=700)}<rect x="{progress_x}" y="770" width="{progress_width}" height="5" fill="#273442"/><rect x="{progress_x}" y="770" width="{progress_width * min(100, float(level.get("progress") or 0)) / 100}" height="5" fill="{PINK}"/>
{text(54, 837, "成绩评级分布", 12, fill="#ffffff", weight=700)}<line x1="54" y1="849" x2="464" y2="849" stroke="#ffffff19"/>{"".join(grade_parts)}<line x1="54" y1="923" x2="464" y2="923" stroke="#ffffff19"/>
{_activity(54, "账号年龄", _account_age(account_days))}{_activity(192, "日均游玩", number(float(stats.get("play_count") or 0) / account_days, 1) + " 次" if account_days else "暂无数据")}{_activity(330, "平均单次", _average_play_time(stats.get("play_time"), stats.get("play_count")))}
{text(54, 1085, user.get("footer") or "", 10, fill="#ffffff")}</g><polygon points="562,0 586,0 511,{HEIGHT} 487,{HEIGHT}" fill="{PINK}"/>
"""


def _identity_row(y: float, label: str, value: str) -> str:
    return f'{text(54, y, label, 13, fill="#ffffff")}{fitted_text(199, y, value, 14, 260, weight=700)}<line x1="54" y1="{y + 14}" x2="464" y2="{y + 14}" stroke="#ffffff17"/>'


def _activity(x: float, label: str, value: str) -> str:
    return f"{text(x, 957, label, 10, fill='#ffffff')}{fitted_text(x, 984, value, 15, 120, fill='#ffffff', weight=700)}"


def _trend(user: dict, x: float, y: float, width: float) -> str:
    stats = user.get("statistics") or {}
    current = stats.get("global_rank")
    values = [float(value) for value in user.get("rank_history") or [] if value is not None]
    if not values or current is None:
        return f"{text(x + 16, y + 28, '90 天排名趋势', 13, fill='#111824', weight=700)}{text(x + 16, y + 51, '暂无排名记录', 10, fill='#111824')}"
    best, worst = min(values), max(values)
    chart_x, chart_y, chart_width, chart_height = x + 175, y + 12, width - 350, 48
    points = []
    for index, value in enumerate(values):
        px = chart_x + index / max(1, len(values) - 1) * chart_width
        py = chart_y + (value - best) / max(1, worst - best) * chart_height
        points.append(f"{px:.1f},{py:.1f}")
    start = values[-14] if len(values) >= 14 else values[0]
    delta = start - values[-1]
    delta_text = f"↑{number(delta)}" if delta > 0 else f"↓{number(abs(delta))}" if delta < 0 else "—"
    return f'{text(x + 16, y + 27, "90 天排名趋势", 13, fill="#111824", weight=700)}{text(x + 16, y + 50, f"最高 #{number(best)} · 最低 #{number(worst)}", 10, fill="#111824")}<line x1="{chart_x}" y1="{chart_y}" x2="{chart_x + chart_width}" y2="{chart_y}" stroke="#bcc7cb" stroke-dasharray="3 4"/><line x1="{chart_x}" y1="{chart_y + chart_height}" x2="{chart_x + chart_width}" y2="{chart_y + chart_height}" stroke="#bcc7cb" stroke-dasharray="3 4"/><polyline points="{" ".join(points)}" fill="none" stroke="{CYAN}" stroke-width="3"/>{text(x + width - 16, y + 27, "当前 #" + number(current), 13, fill="#111824", anchor="end", weight=700)}{text(x + width - 16, y + 50, "近14天 " + delta_text, 10, fill="#0b9d73", anchor="end")}'


def _career_column(x: float, title: str, rows: list[tuple[str, str]], color: str) -> str:
    parts = [
        f'<rect x="{x}" y="349" width="350" height="3" fill="{color}"/>{text(x + 20, 376, title, 13, fill=color, weight=700)}'
    ]
    for index, (label, value) in enumerate(rows):
        y = 406 + index * 37
        parts.append(text(x + 20, y, label, 12, fill="#111824"))
        parts.append(fitted_text(x + 326, y, value, 15, 170, fill="#111824", anchor="end", weight=700))
        if index < len(rows) - 1:
            parts.append(
                f'<line x1="{x + 20}" y1="{y + 12}" x2="{x + 326}" y2="{y + 12}" stroke="#c8ced1" stroke-dasharray="2 3"/>'
            )
    return "".join(parts)


def _badge_description(value: object, x: float, y: float, width: float) -> str:
    remaining = str(value or "徽章")
    lines: list[str] = []
    for _ in range(2):
        if text_width(remaining, 9) <= width:
            lines.append(remaining)
            remaining = ""
            break
        end = len(remaining)
        while end > 1 and text_width(remaining[:end], 9) > width:
            end -= 1
        split = remaining.rfind(" ", 0, end + 1)
        if split > 0:
            end = split
        lines.append(remaining[:end].strip())
        remaining = remaining[end:].strip()
    if remaining and lines:
        lines[-1] = truncate_text(lines[-1] + " " + remaining, width, 9)
    return "".join(
        text(x + width / 2, y + index * 11, line, 9, fill="#111824", anchor="middle", weight=700)
        for index, line in enumerate(lines)
    )


def _badge_row(user: dict, y: float) -> str:
    badges = (user.get("badges") or [])[:8]
    if not badges:
        return ""
    parts = [
        text(645, y + 30, "近期荣誉", 22, fill="#111824", weight=700),
        f'<rect x="751" y="{y + 22}" width="25" height="4" fill="{PINK}"/><rect x="776" y="{y + 22}" width="13" height="4" fill="{CYAN}"/>',
        text(
            1680,
            y + 30,
            f"最近 {len(badges)} 枚 / 共 {len(user.get('badges') or [])} 枚",
            11,
            fill="#111824",
            anchor="end",
        ),
    ]
    gap = 12
    card_width = (1035 - gap * 7) / 8
    for index, badge in enumerate(badges):
        x = 645 + index * (card_width + gap)
        parts.append(image(badge.get("image_data"), x, y + 48, card_width, 55, contain=True))
        parts.append(_badge_description(badge.get("description"), x + 2, y + 116, card_width - 4))
        parts.append(
            text(
                x + card_width / 2,
                y + 139,
                str(badge.get("awarded_at") or "")[:4],
                10,
                fill=CYAN,
                anchor="middle",
                weight=700,
            )
        )
    return "".join(parts)


def _bp_card(play: dict, index: int, top: float) -> str:
    width, gap = 196, 14
    row, column = divmod(index, 5)
    x = 635 + column * (width + gap)
    y = top + row * 188
    visual_height = 104
    clip_id = f"info-bp-{index}"
    shade_id = f"info-bp-shade-{index}"
    star = float(play.get("stars") or 0)
    return f"""
<defs><clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{width}" height="{visual_height}" rx="7"/></clipPath><linearGradient id="{shade_id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#07111d" stop-opacity="0"/><stop offset="1" stop-color="#07111d" stop-opacity=".72"/></linearGradient></defs><rect x="{x}" y="{y}" width="{width}" height="{visual_height}" rx="7" fill="#101925"/>{image(play.get("cover_data"), x, y, width, visual_height, clip=clip_id)}<rect x="{x}" y="{y + 52}" width="{width}" height="52" fill="url(#{shade_id})" clip-path="url(#{clip_id})"/>
<rect x="{x + 8}" y="{y + 8}" width="30" height="22" rx="11" fill="{PINK}"/>{text(x + 23, y + 24, "#" + str(index + 1), 9, anchor="middle", weight=700)}
{rank_seal(str(play.get("rank") or "A"), x + 42, y + 8, width=42, height=22)}
<rect x="{x + width - 61}" y="{y + 8}" width="53" height="22" rx="11" fill="{star_color(star)}"/>{text(x + width - 34.5, y + 24, number(star, 2) + "★", 9, fill="#101925" if star < 6.5 else "#ffd966", anchor="middle", weight=700)}
{mod_strip(play.get("mods") or [], play.get("speed_changes") or {}, x=x + 8, y=y + 72, icon_size=24, max_width=113, preserve_artwork_ratio=True)}<rect x="{x + width - 75}" y="{y + 72}" width="67" height="24" rx="12" fill="#f2c967"/>{text(x + width - 41.5, y + 89, number(play.get("pp"), 1) + " pp", 10, fill="#17202b", anchor="middle", weight=700)}
{fitted_text(x, y + 127, play.get("title") or "", 13, width, fill="#111824", weight=700)}{fitted_text(x, y + 149, play.get("artist") or "", 10, width - 65, fill="#111824")}{text(x + width, y + 149, number(play.get("accuracy"), 2) + "%", 10, fill=PINK, anchor="end", weight=700)}<line x1="{x}" y1="{y + 157}" x2="{x + width}" y2="{y + 157}" stroke="#c8ced1" stroke-dasharray="2 3"/>{fitted_text(x, y + 169, play.get("version") or "", 9, width - 75, fill="#111824")}{text(x + width, y + 169, str(play.get("ended_at") or "")[:10].replace("-", "."), 9, fill=CYAN, anchor="end")}
"""


def build_info_svg(user: dict) -> str:
    stats = user.get("statistics") or {}
    grades = stats.get("grade_counts") or {}
    bp = (user.get("best_plays") or [])[:10]
    has_badges = bool(user.get("badges"))
    badge_y = 503
    divider_y = 671 if has_badges else 520
    bp_header_y = 679 if has_badges else 528
    bp_top = 729 if has_badges else 578
    career = "".join(
        (
            _career_column(
                625,
                "游玩",
                [
                    ("游玩次数", number(stats.get("play_count")) + _change(user.get("pc_change"))),
                    ("游玩时间", _compact(stats.get("play_time")) + "s" + _change(user.get("play_time_change"))),
                    ("总命中数", _compact(stats.get("total_hits")) + _change(user.get("hits_change"))),
                ],
                PINK,
            ),
            _career_column(
                975,
                "得分",
                [
                    ("计入排名得分", _compact(stats.get("ranked_score")) + _change(user.get("ranked_score_change"))),
                    ("累计总分", _compact(stats.get("total_score")) + _change(user.get("total_score_change"))),
                    ("评级成绩", number(sum(int(grades.get(key) or 0) for key in ("ssh", "ss", "sh", "s", "a")))),
                ],
                CYAN,
            ),
            _career_column(
                1325,
                "命中",
                [
                    ("准确率", number(stats.get("hit_accuracy"), 4) + "%" + _change(user.get("acc_change"))),
                    ("最大连击", number(stats.get("maximum_combo")) + "x"),
                    ("回放观看", _compact(stats.get("replays_watched_by_others"))),
                ],
                PINK,
            ),
        )
    )
    cards = "".join(_bp_card(play, index, bp_top) for index, play in enumerate(bp))
    rank = "未排名" if stats.get("global_rank") is None else "#" + number(stats.get("global_rank"))
    rank_start, rank_end = _rank_colors(stats)
    pp_text = number(stats.get("pp"), 1)
    pp_unit_x = min(1420, 1075 + text_width(pp_text, 70) + 14)
    country_rank = "—" if stats.get("country_rank") is None else "#" + number(stats.get("country_rank"))
    bp_count_x = 635 + text_width("最佳成绩", 20) + 10
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}"><defs><pattern id="info-dots" width="17" height="17" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#26303a" opacity=".06"/></pattern></defs><rect width="{WIDTH}" height="{HEIGHT}" fill="#f5f1e9"/><rect x="{SIDE}" width="{WIDTH - SIDE}" height="{HEIGHT}" fill="url(#info-dots)"/>{_left(user)}
{text(645, 62, f"玩家表现 / {user.get('mode', '').upper()}模式", 12, fill="#111824", weight=700)}{text(1680, 62, user.get("footer") or "", 11, fill="#111824", anchor="end")}<line x1="645" y1="80" x2="1680" y2="80" stroke="#c8cdd1"/>
{text(645, 117, "全球排名" + _change(user.get("rank_change")), 12, fill="#111824")}{gradient_text(640, 205, rank, 76, rank_start, rank_end, weight=700)}
<rect x="1060" y="102" width="3" height="88" fill="{PINK}"/>{text(1075, 117, "表现分" + _change(user.get("pp_change")), 12, fill="#111824")}{text(1075, 193, pp_text, 70, fill="#111824", weight=700)}{text(pp_unit_x, 193, "pp", 20, fill=PINK, weight=700)}
{text(1075, 224, "地区排名", 12, fill="#111824", weight=700)}{text(1140, 224, f"{user.get('country_code', '--')} {country_rank}" + _change(user.get("country_rank_change")), 17, fill="#111824", weight=700)}
{text(1450, 117, "准确率", 12, fill="#111824")}{text(1450, 147, number(stats.get("hit_accuracy"), 4) + "%", 18, fill="#111824", weight=700)}{text(1450, 177, "最大连击", 12, fill="#111824")}{text(1450, 207, number(stats.get("maximum_combo")) + "x", 18, fill="#111824", weight=700)}
<rect x="625" y="248" width="1050" height="78" fill="#e8ecec" stroke="#cbd2d5"/><rect x="625" y="248" width="4" height="78" fill="{CYAN}"/>{_trend(user, 625, 248, 1050)}
{career}{_badge_row(user, badge_y)}<line data-role="info-bp-divider" x1="625" y1="{divider_y}" x2="1680" y2="{divider_y}" stroke="#c8cdd1"/><rect x="625" y="{divider_y - 2}" width="86" height="3" fill="{PINK}"/>
{text(635, bp_header_y + 23, "最佳成绩", 20, fill="#111824", weight=700)}{text(bp_count_x, bp_header_y + 23, f"/ 前 {len(bp)}", 14, fill=PINK, weight=700)}{text(1680, bp_header_y + 23, f"平均 PP {number(sum(float(item.get('pp') or 0) for item in bp) / max(1, len(bp)), 2)}  ·  平均准确率 {number(sum(float(item.get('accuracy') or 0) for item in bp) / max(1, len(bp)), 2)}%  ·  最高星数 {number(max((float(item.get('stars') or 0) for item in bp), default=0), 2)}★", 11, fill="#111824", anchor="end")}{cards}</svg>"""
    return svg


async def render_info_svg(user: dict):
    return await render_svg_jpeg_async(
        build_info_svg(user),
        width=WIDTH,
        height=HEIGHT,
        quality=92,
        image_rendering="optimize_speed",
    )
