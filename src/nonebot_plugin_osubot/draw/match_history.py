import re
import asyncio
from pathlib import Path
from datetime import datetime
from statistics import mode

from ..api import api_info
from ..match_room import convert_room_to_match, is_room_response
from ..schema.match import Match
from .image_utils import compress_jpeg
from .match_svg import render_match_svg
from .native_assets import image_source_data_uri


MOD_PATH = Path(__file__).parent.parent / "osufile" / "mods"

# ============ 分页配置（可按需调整） ============
MAX_ROWS_PER_PAGE = 32


def _score_mods(game_mods: list[str], player_mods: list[str]) -> list[str]:
    """合并游戏级 mods 与玩家级 mods，去重并过滤无效/不显示项"""
    mods = list(dict.fromkeys([*game_mods, *player_mods]))
    if "NC" in mods and "DT" in mods:
        mods.remove("DT")
    return [mod for mod in mods if mod not in {"CL", "NM", "FM"} and (MOD_PATH / f"{mod}.png").exists()]


def _match_names(name: str) -> tuple[str, str, str]:
    """从房间名中解析标题和红蓝队名称"""
    matched = re.search(r"([^:]+): [\(（](.+?)[\)）] vs [\(（](.+?)[\)）]", name, re.IGNORECASE)
    if not matched:
        return name, "红队", "蓝队"
    return matched.group(1), matched.group(2), matched.group(3)


def _format_time_range(match: dict) -> tuple[str, str]:
    """格式化比赛时间范围和持续时间文本"""
    start = datetime.fromisoformat(match["start_time"])
    end_value = match.get("end_time")
    if not end_value:
        return f"{start:%Y/%m/%d %H:%M}—进行中", "进行中"
    end = datetime.fromisoformat(end_value)
    duration = int((end - start).total_seconds())
    hours, remainder = divmod(max(duration, 0), 3600)
    minutes = remainder // 60
    duration_text = f"{hours}h {minutes}m" if hours else f"{minutes}m"
    return f"{start:%Y/%m/%d %H:%M}—{end:%H:%M}", duration_text


def _chunk_games(games: list[dict], max_rows: int = MAX_ROWS_PER_PAGE) -> list[list[dict]]:
    """按最大行数将 games 列表分页"""
    chunks: list[list[dict]] = []
    current: list[dict] = []
    rows = 0
    for game in games:
        n = len(game["players"])
        if current and rows + n > max_rows:
            chunks.append(current)
            current, rows = [], 0
        current.append(game)
        rows += n
    if current:
        chunks.append(current)
    return chunks


# ==================== 数据准备 & 渲染 ====================


def prepare_match_data(
    match_info: Match,
    match_id: str,
    team_type_filter: str | None = None,
    *,
    include_failed_scores: bool = False,
) -> dict:
    """将 Match 模型数据转换为模板渲染所需的字典。

    Parameters
    ----------
    team_type_filter : str | None
        只取该模式的 games 渲染（如 "team-vs" / "head-to-head"）。
        用于房间中途切换模式的场景，把不同模式的对局分开渲染。
    """
    all_games = [
        event.game
        for event in match_info.events
        if event.detail.type == "other" and event.game is not None and event.game.scores
    ]
    if not all_games:
        raise ValueError("该多人房没有可展示的对局")

    if team_type_filter:
        games = [game for game in all_games if game.team_type == team_type_filter]
        if not games:
            raise ValueError(f"该多人房没有 {team_type_filter} 模式的对局")
    else:
        games = all_games

    team_type = team_type_filter or mode([game.team_type for game in games])
    is_team = team_type in ("team-vs", "tag-team-vs")
    if is_team:
        _has_team = any((score.match or {}).get("team") in ("red", "blue") for game in games for score in game.scores)
        if not _has_team:
            team_type = "head-to-head"
            is_team = False
    users = {user.id: user for user in match_info.users}
    title, red_name, blue_name = _match_names(match_info.match["name"])
    time_range, duration = _format_time_range(match_info.match)
    red_wins = 0
    blue_wins = 0
    rendered_games: list[dict] = []

    for index, game in enumerate(games, start=1):
        beatmap = game.beatmap
        beatmapset = beatmap.beatmapset if beatmap else None
        scores = (
            [score for score in game.scores if score.user_id is not None]
            if include_failed_scores
            else [score for score in game.scores if score.score > 0]
        )
        if not scores:
            continue

        player_rows: list[dict] = []
        for score in sorted(scores, key=lambda item: item.score or 0, reverse=True):
            user = users.get(score.user_id)
            player_rows.append(
                {
                    "user_id": score.user_id,
                    "name": user.username if user else str(score.user_id),
                    "avatar": user.avatar_url if user else f"https://a.ppy.sh/{score.user_id}",
                    "team": (score.match or {}).get("team", "none"),
                    "passed": (score.match or {}).get("passed", True),
                    "score": score.score or 0,
                    "accuracy": (score.accuracy or 0) * 100,
                    "combo": score.max_combo or 0,
                    "mods": _score_mods(game.mods, score.mods),
                }
            )

        red_score = sum(
            player["score"]
            for player in player_rows
            if player["team"] == "red" and (player["passed"] or not include_failed_scores)
        )
        blue_score = sum(
            player["score"]
            for player in player_rows
            if player["team"] == "blue" and (player["passed"] or not include_failed_scores)
        )
        winner = "none"
        if red_score > blue_score:
            winner = "red"
            red_wins += 1
        elif blue_score > red_score:
            winner = "blue"
            blue_wins += 1

        rendered_games.append(
            {
                "index": index,
                "map_id": game.beatmap_id,
                "title": beatmapset.title if beatmapset else f"Beatmap {game.beatmap_id}",
                "version": beatmap.version if beatmap else "Unknown Difficulty",
                "creator": beatmapset.creator if beatmapset else "unknown",
                "cover": (
                    beatmapset.covers.cover
                    if beatmapset
                    else (f"https://assets.ppy.sh/beatmaps/{beatmap.beatmapset_id}/covers/cover.jpg" if beatmap else "")
                ),
                "stars": beatmap.difficulty_rating if beatmap else 0,
                "winner": winner,
                "red_score": red_score,
                "blue_score": blue_score,
                "players": player_rows,
                "red_players": [p for p in player_rows if p["team"] == "red"],
                "blue_players": [p for p in player_rows if p["team"] == "blue"],
            }
        )

    if not rendered_games:
        raise ValueError("该多人房没有有效成绩")

    return {
        "match_id": match_id,
        "title": title,
        "team_type": team_type,
        "is_team": is_team,
        "red_name": red_name,
        "blue_name": blue_name,
        "red_wins": red_wins,
        "blue_wins": blue_wins,
        "game_count": len(rendered_games),
        "player_count": len({player["user_id"] for game in rendered_games for player in game["players"]}),
        "team_size": max(
            (max(len(g["red_players"]), len(g["blue_players"])) for g in rendered_games),
            default=0,
        ),
        "duration": duration,
        "time_range": time_range,
        "complete": bool(match_info.match.get("end_time")),
        "games": rendered_games,
    }


async def _prepare_match_assets(data: dict) -> dict:
    games = list(data.get("games") or [])
    cover_sources = list(dict.fromkeys(str(game.get("cover") or "") for game in games if game.get("cover")))
    avatar_sources = list(
        {
            (int(player.get("user_id") or 0), str(player.get("avatar") or ""))
            for game in games
            for player in game.get("players") or []
            if player.get("avatar")
        }
    )
    cover_data, avatar_data = await asyncio.gather(
        asyncio.gather(
            *(image_source_data_uri(source, max_size=(304, 224), image_format="JPEG") for source in cover_sources)
        ),
        asyncio.gather(*(image_source_data_uri(source, max_size=(96, 96)) for _user_id, source in avatar_sources)),
    )
    covers = dict(zip(cover_sources, cover_data))
    avatars = dict(zip(avatar_sources, avatar_data))

    def player_row(player: dict) -> dict:
        key = (int(player.get("user_id") or 0), str(player.get("avatar") or ""))
        return {**player, "avatar_data": avatars.get(key)}

    prepared_games = []
    for game in games:
        players = [player_row(player) for player in game.get("players") or []]
        red_players = [player_row(player) for player in game.get("red_players") or []]
        blue_players = [player_row(player) for player in game.get("blue_players") or []]
        prepared_games.append(
            {
                **game,
                "cover_data": covers.get(str(game.get("cover") or "")),
                "players": players,
                "red_players": red_players,
                "blue_players": blue_players,
            }
        )
    return {**data, "games": prepared_games}


async def draw_match_card(data: dict) -> bytes:
    """使用原生 SVG + resvg 渲染单页比赛卡片。"""
    return await render_match_svg(await _prepare_match_assets(data))


async def draw_match_history(
    match_id: str,
    query_type: str = "auto",
    *,
    return_data: bool = False,
) -> list[bytes] | tuple[bytes, dict]:
    """
    绘制多人房/比赛历史记录图片（入口函数）。

    Parameters
    ----------
    match_id : str
        比赛 ID 或多人房 ID。
    query_type : str
        "match" — 仅查询 /matches/ API（传统 mp lobby）
        "room"  — 仅查询 /rooms/ API（osu!lazer multiplayer room）
        "auto"  — 先试 matches，失败再试 rooms（默认）

    Returns
    -------
    list[bytes]
        每页一张 PNG/JPEG 图片字节。
    """
    raw = None
    source = None  # "matches" | "rooms"

    # ── Step 1: 尝试获取原始数据 ──
    if query_type in ("match", "auto"):
        try:
            raw = await api_info("matches", f"https://osu.ppy.sh/api/v2/matches/{match_id}")
            source = "matches"
        except Exception:
            raw = None

    if raw is None and query_type in ("room", "auto"):
        try:
            raw = await api_info("matches", f"https://osu.ppy.sh/api/v2/rooms/{match_id}")
            source = "rooms"
        except Exception:
            raw = None

    if raw is None:
        from ..exceptions import NetworkError as OsubotNetworkError

        raise OsubotNetworkError(f"未找到 ID 为 {match_id} 的比赛/多人房，请检查 ID 是否正确。")

    # ── Step 2: 如果是 rooms 格式，转换为 matches 格式 ──
    is_room = source == "rooms" or is_room_response(raw)
    if is_room:
        raw = await convert_room_to_match(raw, match_id)

    # ── Step 3: 按模式分组渲染 ──
    # 房间可能在运行中切换模式（如热身 head-to-head → 正赛 team-vs），
    # 每种模式分别渲染一张（或多张分页）图片。
    match_info = Match(**raw)
    all_games = [
        event.game
        for event in match_info.events
        if event.detail.type == "other" and event.game is not None and event.game.scores
    ]
    if not all_games:
        raise ValueError("该多人房没有可展示的对局")

    # 找出实际存在的模式（保持稳定顺序：team 类在前，其余在后）
    modes = list(dict.fromkeys(game.team_type for game in all_games))
    team_modes = [mode_type for mode_type in ("team-vs", "tag-team-vs") if mode_type in modes]
    other_modes = [mode_type for mode_type in modes if mode_type not in ("team-vs", "tag-team-vs")]
    ordered_modes = team_modes + other_modes

    pages: list[bytes] = []
    for mode_type in ordered_modes:
        data = prepare_match_data(
            match_info,
            match_id,
            team_type_filter=mode_type,
            include_failed_scores=is_room,
        )
        chunks = _chunk_games(data["games"])
        page_count = len(chunks)

        # agent_tools 的兼容入口只消费一张图片和结构化数据；避免把其余页面
        # 都交给 Playwright 渲染后再丢弃。
        if return_data:
            page_data = {
                **data,
                "games": chunks[0],
                "page_index": 1,
                "page_count": page_count,
            }
            img = await draw_match_card(page_data)
            return compress_jpeg(img), data

        for page_index, chunk in enumerate(chunks, start=1):
            page_data = {
                **data,
                "games": chunk,
                "page_index": page_index,
                "page_count": page_count,
            }
            img = await draw_match_card(page_data)
            pages.append(compress_jpeg(img))

    return pages
