"""Native SVG renderer for multiplayer match history cards."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from .svg_components import fitted_text, image, mod_strip, star_color, text
from .svg_render import render_svg_jpeg_async, text_width, truncate_text


TEAM_WIDTH = 1280
H2H_WIDTH = 900
TEAM_HEADER = 196
H2H_HEADER = 160
TEAM_MARGIN = 42
H2H_MARGIN = 30
GAME_GAP = 20
FOOTER_SPACE = 60
MIN_HEIGHT = 900

BG = "#091521"
PANEL = "#0c1925"
PINK = "#f04483"
RED = "#ff6289"
BLUE = "#51d0dd"
MUTED = "#8195a3"
DIM = "#526c7c"


def _score(value: object) -> str:
    try:
        return f"{int(value or 0):,}"
    except (TypeError, ValueError):
        return "0"


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _avatar(player: dict, x: float, y: float, size: float, clip_id: str) -> str:
    cx = x + size / 2
    cy = y + size / 2
    return f"""<defs><clipPath id="{clip_id}"><circle cx="{cx}" cy="{cy}" r="{size / 2}"/></clipPath></defs><circle cx="{cx}" cy="{cy}" r="{size / 2}" fill="#263744"/>{image(player.get("avatar_data"), x, y, size, size, clip=clip_id)}"""


def _star_chip(stars: float, x: float, y: float) -> str:
    color = star_color(stars)
    return f'<rect x="{x}" y="{y}" width="64" height="23" rx="3" fill="#07111c" stroke="#ffffff" stroke-opacity=".11"/><rect x="{x}" y="{y}" width="4" height="23" rx="2" fill="{color}"/>{text(x + 36, y + 16, f"★ {stars:.2f}", 10, anchor="middle", weight=800)}'


def _map_head(game: dict, x: float, y: float, width: float, *, h2h: bool) -> str:
    cover_width = 64 if h2h else 76
    cover_height = 54 if h2h else 56
    cover_x = x + (14 if h2h else 18)
    cover_y = y + (20 if h2h else 18)
    info_x = cover_x + cover_width + (14 if h2h else 16)
    round_width = 130 if h2h else 250
    round_right = x + width - (14 if h2h else 18)
    info_width = round_right - round_width - info_x - 16
    clip_id = f"match-cover-{game.get('index', 0)}-{'h' if h2h else 't'}"
    title = f"{int(game.get('index') or 0):02d} · {game.get('title') or 'Unknown beatmap'}"
    meta = truncate_text(
        f"{game.get('version') or 'Unknown Difficulty'} · mapped by {game.get('creator') or 'unknown'}",
        max(0, info_width - 72),
        10 if h2h else 11,
    )
    meta_size = 10 if h2h else 11
    star_x = min(info_x + text_width(meta, meta_size) + 9, info_x + info_width - 64)
    parts = [
        f'<defs><clipPath id="{clip_id}"><rect x="{cover_x}" y="{cover_y}" width="{cover_width}" height="{cover_height}" rx="6"/></clipPath></defs>',
        f'<rect x="{cover_x}" y="{cover_y}" width="{cover_width}" height="{cover_height}" rx="6" fill="#263744"/>',
        image(game.get("cover_data"), cover_x, cover_y, cover_width, cover_height, clip=clip_id),
        fitted_text(info_x, y + 40, title, 17 if h2h else 19, info_width, weight=800),
        text(info_x, y + 64, meta, meta_size, fill="#ffffff"),
        _star_chip(_float(game.get("stars")), star_x, y + 49),
    ]
    if h2h:
        parts.extend(
            [
                text(round_right, y + 39, f"{len(game.get('players') or [])} 名选手", 17, anchor="end", weight=800),
                text(round_right, y + 59, "本局完整排名", 10, anchor="end"),
            ]
        )
    else:
        red_score = _float(game.get("red_score")) / 1_000_000
        blue_score = _float(game.get("blue_score")) / 1_000_000
        score_text = f"{red_score:.2f}M : {blue_score:.2f}M"
        parts.append(text(round_right, y + 37, score_text, 20, anchor="end", weight=800))
        winner = game.get("winner")
        if winner in {"red", "blue"}:
            winner_name = game.get("red_name") if winner == "red" else game.get("blue_name")
            label = f"{winner_name or ('红队' if winner == 'red' else '蓝队')} · WIN"
            badge_width = min(170, text_width(label, 10) + 18)
            badge_x = round_right - badge_width
            color = "#e94774" if winner == "red" else "#20aebf"
            parts.extend(
                [
                    f'<rect x="{badge_x}" y="{y + 51}" width="{badge_width}" height="23" rx="3" fill="{color}"/>',
                    fitted_text(round_right - 9, y + 67, label, 10, badge_width - 18, anchor="end", weight=800),
                ]
            )
        else:
            parts.append(text(round_right, y + 65, "本局平局", 10, anchor="end"))
    return "".join(parts)


def _team_side(
    players: list[dict],
    x: float,
    y: float,
    width: float,
    *,
    team: str,
    winner: str,
    game_index: int,
    total_rows: int,
) -> str:
    accent = RED if team == "red" else BLUE
    score_x = x + 237
    acc_x = x + 345
    combo_x = x + 417
    mods_x = x + 499
    parts = []
    if winner == team:
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{34 + 52 * total_rows}" fill="{accent}" fill-opacity=".055"/>'
        )
        side_edge = x if team == "red" else x + width - 4
        parts.append(f'<rect x="{side_edge}" y="{y}" width="4" height="{34 + 52 * total_rows}" fill="{accent}"/>')
    parts.extend(
        [
            f'<line x1="{x}" y1="{y + 33}" x2="{x + width}" y2="{y + 33}" stroke="{accent}" stroke-width="2"/>',
            text(x + 13, y + 22, f"{team.upper()} SIDE · PLAYER", 9, fill=accent, weight=800),
            text(score_x, y + 22, "分数", 9, fill=accent, weight=800),
            text(acc_x, y + 22, "ACC", 9, fill=accent, weight=800),
            text(combo_x, y + 22, "COMBO", 9, fill=accent, weight=800),
            text(mods_x, y + 22, "MODS", 9, fill=accent, weight=800),
        ]
    )
    for player_index, player in enumerate(players):
        row_y = y + 34 + player_index * 52
        avatar_x = x + 13
        parts.extend(
            [
                _avatar(player, avatar_x, row_y + 9, 34, f"match-team-avatar-{game_index}-{team}-{player_index}"),
                fitted_text(
                    avatar_x + 44,
                    row_y + 31,
                    player.get("name") or player.get("user_id") or "player",
                    13,
                    score_x - avatar_x - 55,
                    weight=700,
                ),
                text(score_x, row_y + 23, _score(player.get("score")), 13, weight=700),
                text(score_x, row_y + 38, "分数", 8),
                text(acc_x, row_y + 23, f"{_float(player.get('accuracy')):.2f}%", 13, weight=700),
                text(acc_x, row_y + 38, "准确率", 8),
                text(combo_x, row_y + 23, f"{int(player.get('combo') or 0)}x", 13, weight=700),
                text(combo_x, row_y + 38, "连击", 8),
                mod_strip(
                    player.get("mods") or [],
                    {},
                    x=mods_x,
                    y=row_y + 12,
                    icon_size=27,
                    max_width=max(0, x + width - mods_x - 8),
                    item_gap=-5,
                ),
                f'<line x1="{x}" y1="{row_y + 52}" x2="{x + width}" y2="{row_y + 52}" stroke="#ffffff" stroke-opacity=".05"/>',
            ]
        )
    return "".join(parts)


def _team_game(game: dict, x: float, y: float, width: float, payload: dict) -> tuple[str, float]:
    red_players = list(game.get("red_players") or [])
    blue_players = list(game.get("blue_players") or [])
    rows = max(len(red_players), len(blue_players))
    height = 92 + 34 + 52 * rows
    game_data = {**game, "red_name": payload.get("red_name"), "blue_name": payload.get("blue_name")}
    side_y = y + 92
    half = width / 2
    winner = str(game.get("winner") or "none")
    return (
        f"""<g data-role="match-game"><rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{PANEL}" fill-opacity=".93" stroke="#ffffff" stroke-opacity=".09"/>{_map_head(game_data, x, y, width, h2h=False)}<line x1="{x}" y1="{side_y}" x2="{x + width}" y2="{side_y}" stroke="#ffffff" stroke-opacity=".09"/><line x1="{x + half}" y1="{side_y}" x2="{x + half}" y2="{y + height}" stroke="#ffffff" stroke-opacity=".09"/>{_team_side(red_players, x, side_y, half, team="red", winner=winner, game_index=int(game.get("index") or 0), total_rows=rows)}{_team_side(blue_players, x + half, side_y, half, team="blue", winner=winner, game_index=int(game.get("index") or 0), total_rows=rows)}</g>""",
        height,
    )


def _h2h_game(game: dict, x: float, y: float, width: float) -> tuple[str, float]:
    players = list(game.get("players") or [])
    height = 94 + 38 + 62 * len(players)
    rank_x = x + 14
    player_x = x + 66
    score_x = x + 396
    performance_x = x + 538
    mods_x = x + 714
    parts = [
        f'<g data-role="match-game"><rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{PANEL}" fill-opacity=".93" stroke="#ffffff" stroke-opacity=".09"/>',
        _map_head(game, x, y, width, h2h=True),
        f'<line x1="{x}" y1="{y + 94}" x2="{x + width}" y2="{y + 94}" stroke="#ffffff" stroke-opacity=".09"/>',
        text(rank_x, y + 119, "排名", 10, weight=800),
        text(player_x, y + 119, "玩家", 10, weight=800),
        text(score_x, y + 119, "分数", 10, weight=800),
        text(performance_x, y + 119, "表现", 10, weight=800),
        text(mods_x, y + 119, "MODS", 10, weight=800),
    ]
    for index, player in enumerate(players):
        row_y = y + 132 + index * 62
        if index == 0:
            parts.extend(
                [
                    f'<rect x="{x}" y="{row_y}" width="{width}" height="62" fill="{PINK}" fill-opacity=".09"/>',
                    f'<rect x="{x}" y="{row_y}" width="3" height="62" fill="{PINK}"/>',
                ]
            )
        parts.extend(
            [
                text(rank_x, row_y + 38, f"#{index + 1}", 18, fill=PINK if index == 0 else "#ffffff", weight=800),
                _avatar(player, player_x, row_y + 11.5, 39, f"match-h2h-avatar-{int(game.get('index') or 0)}-{index}"),
                fitted_text(
                    player_x + 49,
                    row_y + 37,
                    player.get("name") or player.get("user_id") or "player",
                    15,
                    score_x - player_x - 60,
                    weight=700,
                ),
                text(score_x, row_y + 28, _score(player.get("score")), 15, weight=700),
                text(score_x, row_y + 44, "分数", 8),
                text(performance_x, row_y + 28, f"{_float(player.get('accuracy')):.2f}%", 15, weight=700),
                text(performance_x, row_y + 44, "准确率", 8),
                text(performance_x + 88, row_y + 28, f"{int(player.get('combo') or 0)}x", 15, weight=700),
                text(performance_x + 88, row_y + 44, "最大连击", 8),
                mod_strip(
                    player.get("mods") or [],
                    {},
                    x=mods_x,
                    y=row_y + 16,
                    icon_size=30,
                    max_width=max(0, x + width - mods_x - 8),
                    item_gap=-6,
                ),
                f'<line x1="{x}" y1="{row_y + 62}" x2="{x + width}" y2="{row_y + 62}" stroke="#ffffff" stroke-opacity=".05"/>',
            ]
        )
    parts.append("</g>")
    return "".join(parts), height


def _team_header(payload: dict) -> str:
    return f"""<rect width="{TEAM_WIDTH}" height="{TEAM_HEADER}" fill="#0b1926"/><rect width="{TEAM_WIDTH}" height="{TEAM_HEADER}" fill="url(#match-head-glow)"/>{text(44, 52, "MULTIPLAYER · FULL SCOREBOARD", 12, fill=PINK, weight=800)}{fitted_text(44, 99, payload.get("title") or "Multiplayer Match", 39, 780, weight=800)}
{text(1236, 52, f"MP {payload.get('match_id') or ''}", 12, anchor="end")}{text(1236, 74, f"{int(payload.get('game_count') or 0)} 局 · TEAM VS · {int(payload.get('team_size') or 0)}v{int(payload.get('team_size') or 0)}", 12, anchor="end")}
{fitted_text(44, 171, payload.get("red_name") or "红队", 20, 420, fill=RED, weight=800)}{text(640, 165, f"{int(payload.get('red_wins') or 0)} : {int(payload.get('blue_wins') or 0)}", 31, anchor="middle", weight=800)}{text(640, 181, "MATCH COMPLETE" if payload.get("complete") else "MATCH IN PROGRESS", 9, anchor="middle")}{fitted_text(1236, 171, payload.get("blue_name") or "蓝队", 20, 420, fill=BLUE, anchor="end", weight=800)}<line x1="0" y1="195.5" x2="1280" y2="195.5" stroke="#ffffff" stroke-opacity=".09"/>"""


def _h2h_header(payload: dict) -> str:
    return f"""<rect width="{H2H_WIDTH}" height="{H2H_HEADER}" fill="#0b1926"/><rect width="{H2H_WIDTH}" height="{H2H_HEADER}" fill="url(#match-head-glow)"/>{text(36, 50, "HEAD-TO-HEAD · FULL SCOREBOARD", 12, fill=PINK, weight=800)}{fitted_text(36, 96, f"个人混战战报 / {payload.get('title') or 'Multiplayer Match'}", 33, 620, weight=800)}
{text(864, 50, f"MP {payload.get('match_id') or ''}", 12, anchor="end")}{text(864, 72, f"{int(payload.get('game_count') or 0)} 局 · {int(payload.get('player_count') or 0)} 名选手 · {'MATCH COMPLETE' if payload.get('complete') else 'IN PROGRESS'}", 12, anchor="end")}<line x1="0" y1="159.5" x2="900" y2="159.5" stroke="#ffffff" stroke-opacity=".09"/>"""


def build_match_svg(payload: dict) -> tuple[str, int, int]:
    is_team = bool(payload.get("is_team"))
    width = TEAM_WIDTH if is_team else H2H_WIDTH
    header_height = TEAM_HEADER if is_team else H2H_HEADER
    margin = TEAM_MARGIN if is_team else H2H_MARGIN
    game_width = width - margin * 2
    cursor_y = header_height + (22 if is_team else 20)
    game_parts = []
    for game in payload.get("games") or []:
        game_svg, game_height = (
            _team_game(game, margin, cursor_y, game_width, payload)
            if is_team
            else _h2h_game(game, margin, cursor_y, game_width)
        )
        game_parts.append(game_svg)
        cursor_y += game_height + GAME_GAP
    if game_parts:
        cursor_y -= GAME_GAP
    height = max(MIN_HEIGHT, round(cursor_y + 16 + FOOTER_SPACE))
    page_index = int(payload.get("page_index") or 1)
    page_count = int(payload.get("page_count") or 1)
    footer_right = "OSUBOT MULTIPLAYER HISTORY" if is_team else "OSUBOT HEAD-TO-HEAD HISTORY"
    if page_count > 1:
        footer_right += f" · {page_index}/{page_count}"
    header = _team_header(payload) if is_team else _h2h_header(payload)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><defs><radialGradient id="match-head-glow" cx="84%" cy="0" r="45%"><stop stop-color="#8d3267" stop-opacity=".34"/><stop offset="1" stop-color="#8d3267" stop-opacity="0"/></radialGradient><pattern id="match-grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="#ffffff" stroke-opacity=".025"/></pattern></defs><rect width="{width}" height="{height}" fill="{BG}"/><rect width="{width}" height="{height}" fill="url(#match-grid)"/>{header}{"".join(game_parts)}{text(margin, height - 20, payload.get("time_range") or "", 10, fill=DIM)}{text(width - margin, height - 20, footer_right, 10, fill=DIM, anchor="end")}</svg>"""
    return svg, width, height


async def render_match_svg(payload: dict) -> bytes:
    svg, width, height = build_match_svg(payload)
    result = await render_svg_jpeg_async(svg, width=width, height=height, quality=92)
    return result.getvalue()
