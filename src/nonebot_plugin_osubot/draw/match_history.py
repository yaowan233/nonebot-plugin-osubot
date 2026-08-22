import io
import re
from pathlib import Path
from datetime import datetime
from statistics import mode

import jinja2

try:  # Pillow 可选依赖：用于压缩图片；未安装时自动回退为原图
    from PIL import Image

    _HAS_PIL = True
except ImportError:  # pragma: no cover
    _HAS_PIL = False

from ..api import api_info
from ..schema.match import Match
from .browser import persistent_page
from nonebot.log import logger


TEMPLATE_PATH = Path(__file__).parent / "match_templates"
MOD_PATH = Path(__file__).parent.parent / "osufile" / "mods"

# ============ 分页 / 压缩配置（可按需调整） ============
MAX_ROWS_PER_PAGE = 32
MAX_IMAGE_WIDTH = 1200
JPEG_QUALITY = 85
BG_COLOR = (13, 13, 20)

# ============ Rooms API type → Match schema team_type 映射 ============
_ROOM_TYPE_MAP: dict[str, str] = {
    "team_versus": "team-vs",
    "head_to_head": "head-to-head",
    "tag_coop": "tag-coop",
    "tag_team_vs": "tag-team-vs",
}


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
    chunks: list[dict] = []
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


def _compress_image(img_bytes: bytes) -> bytes:
    """使用 Pillow 压缩截图；未安装或失败时返回原图"""
    if not _HAS_PIL:
        return img_bytes
    try:
        im = Image.open(io.BytesIO(img_bytes))
        if im.width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / im.width
            im = im.resize((MAX_IMAGE_WIDTH, int(im.height * ratio)), Image.LANCZOS)
        if im.mode != "RGB":
            background = Image.new("RGB", im.size, BG_COLOR)
            im = im.convert("RGBA")
            background.paste(im, mask=im.split()[-1])
            im = background
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception:
        return img_bytes


def _merge_images_vertically(pages: list[bytes]) -> bytes:
    """将多页图片纵向拼接为一张长图"""
    if not _HAS_PIL or len(pages) <= 1:
        return pages[0] if pages else b""
    try:
        images = [Image.open(io.BytesIO(p)) for p in pages]
        total_width = max(im.width for im in images)
        total_height = sum(im.height for im in images)
        merged = Image.new("RGB", (total_width, total_height), BG_COLOR)
        y_offset = 0
        for im in images:
            if im.mode != "RGB":
                bg = Image.new("RGB", im.size, BG_COLOR)
                bg.paste(im, mask=im.split()[-1])
                im = bg
            merged.paste(im, (0, y_offset))
            y_offset += im.height
        buf = io.BytesIO()
        merged.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception:
        return pages[0]


# ==================== Rooms API 适配层 ====================


def _is_rooms_response(raw: dict) -> bool:
    """
    判断 API 返回的是 /rooms/ 格式还是 /matches/ 格式。

    /matches/ 响应一定有顶层 "match" 键；
    /rooms/ 响应有 "playlist" 或 "category" 键，且没有 "match"。
    """
    return "match" not in raw and ("playlist" in raw or "category" in raw)


def _parse_mods(raw_mods: list) -> list[str]:
    """
    将 osu! API v2 返回的 mods 列表统一为 acronym 字符串列表。

    API 可能返回两种格式：
      - 字符串列表: ["HD", "DT"]
      - 对象列表:   [{"acronym": "HD", ...}, {"acronym": "DT", ...}]
    """
    result: list[str] = []
    for m in raw_mods:
        if isinstance(m, dict):
            acronym = m.get("acronym", "")
            if acronym:
                result.append(acronym)
        elif isinstance(m, str) and m:
            result.append(m)
    return result


async def _fetch_room_team_map(
    match_id: str,
) -> tuple[dict[int, dict[str, str]], dict[str, str] | None, set[int], dict[int, str]]:
    """
    从 /api/v2/rooms/{id}/events 接口解析：
      1. 每个 playlist item 的红蓝分队映射
      2. 被强制关闭(abort)的 playlist_item_id 集合
      3. 每个 playlist item 自己的真实模式（details.room_type）

    osu! 官方页面渲染 --red/--blue 的数据来源就是 events 接口里
    每个 playlist_item.details.teams，结构为：
        { "user_id字符串": "red" | "blue" }

    注意：同一房间可能在运行中切换模式（如先 head_to_head 热身、后 team_versus
    正赛），因此**每个 playlist item 单独记录自己的 room_type**，顶层 /rooms/{id}
    的 type 字段只作为兜底。

    而被强制关闭的对局在 events 流里有 event_type == "game_aborted"
    （正常完成的是 "game_completed"），据此可精确剔除 abort 局。

    Returns
    -------
    pid_teams : dict[int, dict[str, str]]
        按 playlist_item_id 索引的精确队伍映射：{ pid: { uid_str: "red"/"blue" } }
    fallback_teams : dict[str, str] | None
        全局兜底映射（合并所有 item 的 teams），用于无法精确匹配 pid 的场景。
        解析失败时返回 None。
    aborted_pids : set[int]
        被强制关闭(game_aborted)的 playlist_item_id 集合。
    pid_room_types : dict[int, str]
        按 playlist_item_id 索引的房间模式（原始值如 "team_versus"/"head_to_head"），
        该 item 解析不到时不存在于字典中。
    """
    events_url = f"https://osu.ppy.sh/api/v2/rooms/{match_id}/events"

    pid_teams: dict[int, dict[str, str]] = {}
    fallback_teams: dict[str, str] = {}
    aborted_pids: set[int] = set()
    pid_room_types: dict[int, str] = {}

    try:
        events_data = await api_info("matches", events_url)
    except Exception as exc:
        logger.debug(f"[team-map] room {match_id}: 请求 events 失败，降级 head-to-head ({exc})")
        return {}, None, set(), {}

    # ── 从 events 流提取 game_aborted 的 playlist_item_id ──
    raw_events: list = []
    if isinstance(events_data, dict):
        raw_events = events_data.get("events", []) or []
    for ev in raw_events:
        if not isinstance(ev, dict):
            continue
        if ev.get("event_type") == "game_aborted":
            pid = ev.get("playlist_item_id")
            if pid is not None:
                try:
                    aborted_pids.add(int(pid))
                except (TypeError, ValueError):
                    pass

    # events 接口的 playlist items 可能在 "playlist" 或 "events" 里，做兼容
    playlist_items: list[dict] = []
    if isinstance(events_data, dict):
        playlist_items = events_data.get("playlist") or events_data.get("playlist_items") or []
        # 部分版本 events 是事件流，playlist item 嵌在 event.playlist_item 里
        if not playlist_items:
            for ev in raw_events:
                pi = ev.get("playlist_item") if isinstance(ev, dict) else None
                if isinstance(pi, dict):
                    playlist_items.append(pi)

    for item in playlist_items:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        details = item.get("details") or {}

        # ── 记录该 item 自己的房间模式 ──
        rt_raw = details.get("room_type")
        if rt_raw and pid is not None:
            try:
                pid_room_types[int(pid)] = str(rt_raw)
            except (TypeError, ValueError):
                pass

        teams_raw = details.get("teams") or {}

        if not isinstance(teams_raw, dict) or not teams_raw:
            continue

        # 规范化：key 统一为字符串，value 仅保留 red/blue
        norm_map: dict[str, str] = {}
        for uid_key, colour in teams_raw.items():
            if colour in ("red", "blue"):
                norm_map[str(uid_key)] = colour

        if not norm_map:
            continue

        if pid is not None:
            try:
                pid_teams[int(pid)] = norm_map
            except (TypeError, ValueError):
                pass

        # 累积到全局兜底（后出现的覆盖先出现的，同房间队伍一般稳定）
        fallback_teams.update(norm_map)

    if not fallback_teams:
        logger.debug(f"[team-map] room {match_id}: events 中未解析到 teams，降级 head-to-head")

    if aborted_pids:
        logger.debug(f"[team-map] room {match_id}: 检测到 {len(aborted_pids)} 局被强制关闭(abort)")

    if pid_room_types:
        logger.debug(
            f"[team-map] room {match_id}: events 解析到 {len(pid_room_types)} 个 item 的模式"
            f"（分布: {sorted(set(pid_room_types.values()))}）"
        )

    return pid_teams, (fallback_teams or None), aborted_pids, pid_room_types


async def _convert_rooms_to_match_format(raw: dict, match_id: str) -> dict:
    """
    将 /api/v2/rooms/{id} 的响应转换为 Match schema 期望的 /matches/ 格式。

    核心流程：
      1. 构造 match 元信息
      2. 收集用户信息
      3. 从 events 接口获取 team 映射（红蓝分队）
      4. 遍历 playlist，逐个请求 scores 并注入 team
      5. 组装为 matches 格式
    """

    # ── 1. 构造 match 元信息 ──
    match_meta = {
        "id": raw.get("id"),
        "name": raw.get("name", ""),
        "start_time": raw.get("starts_at") or raw.get("created_at", ""),
        "end_time": raw.get("ends_at"),
    }

    # ── 2. 收集用户信息 ──
    users_dict: dict[int, dict] = {}

    host = raw.get("host")
    if host and host.get("id"):
        users_dict[host["id"]] = host

    for participant in raw.get("recent_participants", []):
        uid = participant.get("id")
        if uid and uid not in users_dict:
            users_dict[uid] = participant

    # ── 3. 获取 team 映射 + abort 局集合 + 每个 item 自己的房间模式 ──
    # 注意：顶层 /rooms/{id} 的 type 字段有时不可靠（如 team-vs 房间可能返回
    # head_to_head），且房间可能在运行中切换模式（热身 head_to_head → 正赛
    # team_versus），因此以 events 接口每个 playlist item 的 details.room_type 为准。
    fallback_room_type_raw = raw.get("type", "head_to_head")

    # events 接口对所有模式都有用（abort 判定通用），team 模式额外拿分队
    pid_teams: dict[int, dict[str, str]] = {}
    fallback_teams: dict[str, str] | None = None
    aborted_pids: set[int] = set()
    pid_room_types: dict[int, str] = {}
    pid_teams, fallback_teams, aborted_pids, pid_room_types = await _fetch_room_team_map(match_id)

    # ── 4. 遍历 playlist，逐个请求 scores ──
    playlist = raw.get("playlist", [])
    events: list[dict] = []

    for item in playlist:
        if not item.get("played_at"):
            continue

        playlist_item_id = item["id"]

        # ── 核心：跳过被强制关闭(abort)的对局 ──
        # 依据 events 流里 event_type == "game_aborted" 精确判定。
        if playlist_item_id in aborted_pids:
            logger.debug(f"[rooms] playlist_item {playlist_item_id}: 被强制关闭(abort)，跳过")
            continue

        scores_url = (
            f"https://osu.ppy.sh/api/v2/rooms/{match_id}"
            f"/playlist/{playlist_item_id}/scores"
        )

        try:
            scores_data = await api_info("matches", scores_url)
        except Exception:
            continue

        scores_list = scores_data.get("scores", [])
        if not scores_list:
            continue

        # 收集用户信息
        for s in scores_list:
            user_info = s.get("user")
            if user_info:
                uid = user_info.get("id")
                if uid:
                    if uid not in users_dict:
                        users_dict[uid] = user_info

        # ── 确定本 playlist item 自己的模式与 team 映射 ──
        # 优先使用 events 解析出的该 item 模式；缺失时回退顶层 type。
        item_room_type_raw = pid_room_types.get(playlist_item_id) or fallback_room_type_raw
        item_room_type = _ROOM_TYPE_MAP.get(item_room_type_raw, item_room_type_raw)

        team_map: dict[str, str] = {}
        if item_room_type in ("team-vs", "tag-team-vs"):
            team_map = pid_teams.get(playlist_item_id) or fallback_teams or {}

        game_scores: list[dict] = []
        # ── 只要 score 记录存在就计入（含 fail / HP 归零），并透传 passed ──
        for s in scores_list:
            uid_str = str(s.get("user_id", ""))
            team_colour = team_map.get(uid_str, "none")
            if team_colour not in ("red", "blue"):
                team_colour = "none"

            game_scores.append({
                "user_id": s.get("user_id"),
                "score": s.get("total_score", 0),
                "accuracy": s.get("accuracy", 0),
                "max_combo": s.get("max_combo", 0),
                "mods": _parse_mods(s.get("mods", [])),
                "match": {
                    "team": team_colour,
                    "passed": bool(s.get("passed", True)),  # ← 透传是否通过
                },
            })

        if not game_scores:
            continue

        beatmap_data = item.get("beatmap") or {}
        beatmapset_data = beatmap_data.get("beatmapset") or {}
        covers = beatmapset_data.get("covers") or {}

        cover_url = covers.get("cover", "")
        full_covers = {
            "cover": cover_url,
            "card": covers.get("card", cover_url),
            "list": covers.get("list", cover_url),
            "slimcover": covers.get("slimcover", cover_url),
        }

        game = {
            "id": playlist_item_id,
            "beatmap_id": item.get("beatmap_id"),
            "team_type": item_room_type,
            "mods": _parse_mods(item.get("required_mods", [])),
            "beatmap": {
                "id": beatmap_data.get("id"),
                "mode": beatmap_data.get("mode", "osu"),
                "status": beatmap_data.get("status", "ranked"),
                "total_length": beatmap_data.get("total_length", 0),
                "user_id": beatmap_data.get("user_id", 0),
                "version": beatmap_data.get("version", ""),
                "difficulty_rating": beatmap_data.get("difficulty_rating", 0),
                "beatmapset_id": beatmap_data.get("beatmapset_id"),
                "beatmapset": {
                    "id": beatmapset_data.get("id", beatmap_data.get("beatmapset_id", 0)),
                    "title": beatmapset_data.get("title", ""),
                    "title_unicode": beatmapset_data.get("title_unicode", beatmapset_data.get("title", "")),
                    "artist": beatmapset_data.get("artist", ""),
                    "artist_unicode": beatmapset_data.get("artist_unicode", beatmapset_data.get("artist", "")),
                    "creator": beatmapset_data.get("creator", ""),
                    "user_id": beatmapset_data.get("user_id", 0),
                    "source": beatmapset_data.get("source", ""),
                    "status": beatmapset_data.get("status", "ranked"),
                    "nsfw": beatmapset_data.get("nsfw", False),
                    "video": beatmapset_data.get("video", False),
                    "favourite_count": beatmapset_data.get("favourite_count", 0),
                    "play_count": beatmapset_data.get("play_count", 0),
                    "preview_url": beatmapset_data.get("preview_url", ""),
                    "covers": full_covers,
                },
            },
            "scores": game_scores,
        }

        events.append({
            "id": playlist_item_id,
            "detail": {"type": "other"},
            "timestamp": item.get("played_at", ""),
            "game": game,
        })

    return {
        "match": match_meta,
        "events": events,
        "users": list(users_dict.values()),
    }


# ==================== 数据准备 & 渲染 ====================


def prepare_match_data(match_info: Match, match_id: str, team_type_filter: str | None = None) -> dict:
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
        if event.detail.type == "other"
        and event.game is not None
        and event.game.scores
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
        _has_team = any(
            (score.match or {}).get("team") in ("red", "blue")
            for game in games
            for score in game.scores
        )
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
        # 记录存在即计入（不再按分数过滤）
        scores = [score for score in game.scores if score.user_id is not None]
        if not scores:
            continue

        player_rows: list[dict] = []
        for score in sorted(scores, key=lambda item: item.score or 0, reverse=True):
            user = users.get(score.user_id)
            # ── 队伍标签拼接逻辑 ──
            if user:
                team = getattr(user, "team", None)
                tag = (
                    getattr(team, "short_name", None) or getattr(team, "name", None)
                ) if team else None
                display_name = f"[{tag}] {user.username}" if tag else user.username
            else:
                display_name = str(score.user_id)
            # ── 队伍标签拼接逻辑结束 ──
            player_rows.append({
                "user_id": score.user_id,
                "name": display_name,
                "avatar": user.avatar_url if user else f"https://a.ppy.sh/{score.user_id}",
                "team": (score.match or {}).get("team", "none"),
                "passed": (score.match or {}).get("passed", True),
                "score": score.score or 0,
                "accuracy": (score.accuracy or 0) * 100,
                "combo": score.max_combo or 0,
                "mods": _score_mods(game.mods, score.mods),
            })

        # ── 队伍总分：与 osu! 官方判定一致，只统计通过(passed)玩家的分数 ──
        # 参考 osu-web resources/js/legacy-match/content.tsx：
        #   if (!score.passed) continue; scores[team] += score.total_score;
        red_score = sum(
            p["score"] for p in player_rows
            if p["team"] == "red" and p["passed"]
        )
        blue_score = sum(
            p["score"] for p in player_rows
            if p["team"] == "blue" and p["passed"]
        )
        winner = "none"
        if red_score > blue_score:
            winner = "red"
            red_wins += 1
        elif blue_score > red_score:
            winner = "blue"
            blue_wins += 1

        rendered_games.append({
            "index": index,
            "map_id": game.beatmap_id,
            "title": beatmapset.title if beatmapset else f"Beatmap {game.beatmap_id}",
            "version": beatmap.version if beatmap else "Unknown Difficulty",
            "creator": beatmapset.creator if beatmapset else "unknown",
            "cover": (
                beatmapset.covers.cover
                if beatmapset
                else (
                    f"https://assets.ppy.sh/beatmaps/{beatmap.beatmapset_id}/covers/cover.jpg"
                    if beatmap
                    else ""
                )
            ),
            "stars": beatmap.difficulty_rating if beatmap else 0,
            "winner": winner,
            "red_score": red_score,
            "blue_score": blue_score,
            "players": player_rows,
            "red_players": [p for p in player_rows if p["team"] == "red"],
            "blue_players": [p for p in player_rows if p["team"] == "blue"],
        })

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
        "player_count": len({
            player["user_id"]
            for game in rendered_games
            for player in game["players"]
        }),
        "team_size": max(
            (max(len(g["red_players"]), len(g["blue_players"])) for g in rendered_games),
            default=0,
        ),
        "duration": duration,
        "time_range": time_range,
        "complete": bool(match_info.match.get("end_time")),
        "games": rendered_games,
    }


async def draw_match_card(data: dict) -> bytes:
    """使用 Jinja2 + Playwright 渲染单页比赛卡片并截图"""
    template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(str(TEMPLATE_PATH)), enable_async=True
    ).get_template("index.html")
    async with persistent_page(
        "match_history",
        (TEMPLATE_PATH / "index.html").as_uri(),
        {"width": 1280, "height": 900},
    ) as page:
        await page.set_content(
            await template.render_async(**data), wait_until="domcontentloaded"
        )
        await page.evaluate(
            "Promise.race([Promise.all([document.fonts.ready,"
            "...Array.from(document.images,x=>x.decode().catch(()=>{}))]),"
            "new Promise(resolve=>setTimeout(resolve,8000))])"
        )
        element = await page.query_selector(".card")
        assert element
        return await element.screenshot(type="png")


async def draw_match_history(match_id: str, query_type: str = "auto") -> list[bytes]:
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
            raw = await api_info(
                "matches", f"https://osu.ppy.sh/api/v2/matches/{match_id}"
            )
            source = "matches"
        except Exception:
            raw = None

    if raw is None and query_type in ("room", "auto"):
        try:
            raw = await api_info(
                "matches", f"https://osu.ppy.sh/api/v2/rooms/{match_id}"
            )
            source = "rooms"
        except Exception:
            raw = None

    if raw is None:
        from ..exceptions import NetworkError as OsubotNetworkError
        raise OsubotNetworkError(
            f"未找到 ID 为 {match_id} 的比赛/多人房，请检查 ID 是否正确。"
        )

    # ── Step 2: 如果是 rooms 格式，转换为 matches 格式 ──
    if source == "rooms" or _is_rooms_response(raw):
        raw = await _convert_rooms_to_match_format(raw, match_id)

    # ── Step 3: 按模式分组渲染 ──
    # 房间可能在运行中切换模式（如热身 head-to-head → 正赛 team-vs），
    # 每种模式分别渲染一张（或多张分页）图片。
    match_info = Match(**raw)
    all_games = [
        event.game
        for event in match_info.events
        if event.detail.type == "other"
        and event.game is not None
        and event.game.scores
    ]
    if not all_games:
        raise ValueError("该多人房没有可展示的对局")

    # 找出实际存在的模式（保持稳定顺序：team 类在前，其余在后）
    mode_set: set[str] = {game.team_type for game in all_games}
    team_modes = [m for m in ("team-vs", "tag-team-vs") if m in mode_set]
    other_modes = [m for m in mode_set if m not in ("team-vs", "tag-team-vs")]
    ordered_modes = team_modes + other_modes

    pages: list[bytes] = []
    for mode_type in ordered_modes:
        data = prepare_match_data(match_info, match_id, team_type_filter=mode_type)
        chunks = _chunk_games(data["games"])
        page_count = len(chunks)
        for page_index, chunk in enumerate(chunks, start=1):
            page_data = {
                **data,
                "games": chunk,
                "page_index": page_index,
                "page_count": page_count,
            }
            img = await draw_match_card(page_data)
            pages.append(_compress_image(img))

    return pages