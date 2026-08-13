from __future__ import annotations

import re
import json
import asyncio
import base64
import datetime
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Literal, Annotated
from pathlib import Path

from langchain.tools import tool
from sqlalchemy import select
from nonebot_plugin_orm import get_session
from nonebot_plugin_alconna import UniMessage

from nonebot_plugin_ai_groupmate.agent import AgentToolBundle, AgentToolContext, register_agent_tool
from nonebot_plugin_ai_groupmate.reply_guard import is_request_active

from .api import (
    get_uid_by_name,
    get_osu_user,
    get_recommend,
    get_user_scores,
    osu_api,
    safe_async_get,
    search_beatmapsets,
)
from .draw import draw_info, draw_score, get_score_data, draw_map_info, draw_bmap_info
from .info import get_bg
from .utils import FGM, NGM, mods2list, normalize_map_mode
from .mods import get_mods_list
from .file import download_osu
from .mania import generate_preview_pic
from .database import InfoData, UserData, SbUserData
from .exceptions import NetworkError
from .schema.score import Mod, NewStatistics, UnifiedBeatmap, UnifiedScore
from .schema.user import UnifiedUser
from .schema.alphaosu import RecommendData, RecommendItem
from .draw.score import cal_score_info, draw_selected_score
from .draw.bp import draw_pfm, select_bp_scores
from .draw.rating import draw_rating
from .draw.recommend import draw_recommend
from .draw.echarts import build_bpa_data, draw_bpa_plot, draw_history_plot
from .draw.osu_preview import draw_osu_preview, draw_full_osu_preview
from .draw.match_history import draw_match_history
from .draw.catch_preview import draw_cath_preview
from .draw.taiko_preview import map_to_image, parse_map
from .help_data import get_command_help
from .history_data import merge_osutrack_history
from .matcher.utils import parse_bp_filter_text

ContentBlock = str | dict[str, Any]
UsernameArg = Annotated[
    str | None,
    "osu 用户名。查询当前发言用户或用户说“我/我的/自己”时必须省略；不要填写 QQ/user_id。",
]
TargetUserIdArg = Annotated[
    str | None,
    "群友的 QQ/平台 user_id。仅当用户明确给出该 ID 时填写；查询当前发言用户时必须省略，禁止猜测或追问。",
]
BpPurposeArg = Annotated[
    Literal["view", "analyze"],
    "用户目的。只想查询或看图时填 view；要求评价、分析发挥或找问题时填 analyze。",
]
BpFiltersArg = Annotated[
    str,
    (
        "BP 列表筛选表达式，多个条件用空格连接（AND）。例如 `300pp+ 98a+ 5-7* fc -DT`，或 "
        '`p>=300 a>=98 s=5..7 m=0 mp~kanon t~"Freedom Dive" cl=l`。'
    ),
]
_SELF_REFERENCE_VALUES = {
    "我",
    "自己",
    "本人",
    "当前用户",
    "当前用户id",
    "绑定用户",
    "current_user",
    "current user",
    "current-user",
    "request_user",
    "requester",
}
medal_data_path = Path(__file__).parent / "osufile" / "medals" / "medals.json"
with open(medal_data_path, encoding="utf-8") as file:
    medal_json = json.load(file)


@dataclass(slots=True)
class ResolvedOsuUser:
    user_id: int
    name: str
    default_mode: str = "0"


def _normalize_source(source: str) -> str:
    source = (source or "osu").strip().lower()
    if source in {"sb", "ppysb"}:
        return "ppysb"
    return "osu"


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if value.lower() in {"none", "null", "nil", "undefined"}:
        return None
    if value.lower() in _SELF_REFERENCE_VALUES:
        return None
    return value


def _clean_user_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() in {
        "none",
        "null",
        "nil",
        "undefined",
        "all",
        *_SELF_REFERENCE_VALUES,
    }:
        return None
    return value


def _extract_mentioned_user_id(ctx: AgentToolContext) -> str | None:
    event = getattr(ctx, "event", None)
    if not event:
        return None

    bot_ids = {
        user_id
        for user_id in (
            _clean_user_id(getattr(ctx, "bot_id", None)),
            _clean_user_id(getattr(event, "self_id", None)),
        )
        if user_id
    }
    try:
        message = event.get_message()
    except Exception:
        return None

    for segment in message:
        segment_type = getattr(segment, "type", None)
        data = getattr(segment, "data", {}) or {}
        if segment_type != "at":
            continue
        target = data.get("qq") or data.get("user_id") or data.get("id") or data.get("target")
        target = _clean_user_id(target)
        if target and target not in bot_ids:
            return target
    return None


def _event_user_id(ctx: AgentToolContext) -> str | None:
    if not ctx.event:
        return None
    try:
        return _clean_user_id(ctx.event.get_user_id())
    except Exception:
        return _clean_user_id(getattr(ctx.event, "user_id", None))


def _explicit_target_user_id(
    ctx: AgentToolContext,
    target_user_id: str | int | None = None,
) -> str | None:
    """返回显式目标；非 bot 的 @ 优先于当前发言用户。"""
    bot_ids = {
        user_id
        for user_id in (
            _clean_user_id(getattr(ctx, "bot_id", None)),
            _clean_user_id(getattr(getattr(ctx, "event", None), "self_id", None)),
        )
        if user_id
    }
    for candidate in (
        _clean_user_id(target_user_id),
        _extract_mentioned_user_id(ctx),
    ):
        if candidate and candidate not in bot_ids:
            return candidate
    return None


def _tool_user_id_candidates(ctx: AgentToolContext, target_user_id: str | int | None = None) -> list[str]:
    bot_ids = {
        user_id
        for user_id in (
            _clean_user_id(ctx.bot_id),
            _clean_user_id(getattr(ctx.event, "self_id", None) if ctx.event else None),
        )
        if user_id
    }
    candidates = [
        _clean_user_id(target_user_id),
        _extract_mentioned_user_id(ctx),
        _clean_user_id(ctx.user_id),
        _event_user_id(ctx),
    ]
    result: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in bot_ids or candidate in result:
            continue
        result.append(candidate)
    return result


def _normalize_mode(mode: str | int | None, source: str) -> str | None:
    if mode is None:
        return None
    mode_text = str(mode).strip()
    if not mode_text or mode_text.lower() in {"none", "null", "nil", "undefined"}:
        return None
    allowed = {"0", "1", "2", "3"}
    if source == "ppysb":
        allowed = {"0", "1", "2", "3", "4", "5", "6", "8"}
    if mode_text not in allowed:
        raise ValueError("mode 必须为 0=std, 1=taiko, 2=ctb/fruits, 3=mania；ppysb 还支持 4/5/6/8")
    return mode_text


def _normalize_range(range_text: str | None, default: str = "1-200") -> tuple[int, int]:
    if not range_text or not range_text.strip():
        range_text = default
    parts = range_text.replace(" ", "").split("-", 1)
    if len(parts) != 2:
        raise ValueError("range 必须是类似 1-20 的格式")
    low, high = int(parts[0]), int(parts[1])
    if not 0 < low < high <= 200:
        raise ValueError("range 只支持 1-200 内的递增范围")
    return low, high


def _normalize_firsts_range(range_text: str | None, default: str = "1-30") -> tuple[int, int]:
    if not range_text or not range_text.strip():
        range_text = default
    parts = range_text.replace(" ", "").split("-", 1)
    if len(parts) == 1:
        low = high = int(parts[0])
    else:
        low, high = int(parts[0]), int(parts[1])
    if not 0 < low <= high <= 200:
        raise ValueError("range 只支持 1-200 内的序号或递增范围")
    return low, high


async def _resolve_osu_user(
    ctx: AgentToolContext,
    username: str | None,
    source: str,
    target_user_id: str | int | None = None,
) -> ResolvedOsuUser:
    explicit_target = _explicit_target_user_id(ctx, target_user_id)
    if explicit_target:
        # @ 群友或显式平台 ID 是确定目标，优先级高于模型可能误填的群昵称
        # username。目标未绑定时也不能悄悄回退成查询发言者本人。
        model = SbUserData if source == "ppysb" else UserData
        async with get_session() as session:
            user = await session.scalar(select(model).where(model.user_id == explicit_target))
        if not user:
            bind_command = "/sbbind" if source == "ppysb" else "/bind"
            raise ValueError(f"被查询的群友尚未绑定 osu 账号，请让对方先使用 {bind_command} 用户名")
        return ResolvedOsuUser(
            user.osu_id,
            user.osu_name,
            default_mode=str(getattr(user, "osu_mode", "0")),
        )

    name = _clean_optional_text(username)
    if name:
        if source == "osu":
            info = await get_osu_user(name)
            playmode = str(info.get("playmode") or "osu")
            return ResolvedOsuUser(
                int(info["id"]),
                str(info.get("username") or name),
                default_mode=str(FGM.get(playmode, 0)),
            )
        return ResolvedOsuUser(await get_uid_by_name(name, source), name)

    bind_user_ids = _tool_user_id_candidates(ctx, target_user_id)
    if not bind_user_ids:
        raise ValueError("当前没有可用的用户 ID，请指定 osu 用户名")

    if source == "ppysb":
        async with get_session() as session:
            user = None
            for bind_user_id in bind_user_ids:
                user = await session.scalar(select(SbUserData).where(SbUserData.user_id == bind_user_id))
                if user:
                    break
        if not user:
            raise ValueError("当前用户尚未绑定 osu 账号，请先使用 /sbbind 用户名")
        return ResolvedOsuUser(user.osu_id, user.osu_name)

    async with get_session() as session:
        user = None
        for bind_user_id in bind_user_ids:
            user = await session.scalar(select(UserData).where(UserData.user_id == bind_user_id))
            if user:
                break

    if not user:
        raise ValueError("当前用户尚未绑定 osu 账号，请先使用 /bind 用户名")

    return ResolvedOsuUser(
        user.osu_id,
        user.osu_name,
        default_mode=str(user.osu_mode),
    )


def _resolve_mode(mode: str | int | None, user: ResolvedOsuUser, source: str) -> str:
    return _normalize_mode(mode, source) or _normalize_mode(user.default_mode, source) or "0"


def _resolve_is_lazer(is_lazer: bool | None) -> bool:
    return True if is_lazer is None else is_lazer


async def _send_image(ctx: AgentToolContext, raw: bytes | BytesIO) -> str:
    await UniMessage.image(raw=raw).send(target=ctx.send_target)
    return "已发送图片"


async def _send_text(ctx: AgentToolContext, text: str) -> str:
    await UniMessage.text(text).send(target=ctx.send_target)
    return "已发送文字"


def _to_bytes(raw: bytes | BytesIO) -> bytes:
    if isinstance(raw, BytesIO):
        return raw.getvalue()
    return raw


def _image_tool_result(text: str, raw: bytes | BytesIO, include_image: bool) -> str | list[ContentBlock]:
    if not include_image:
        return text
    image_data = base64.b64encode(_to_bytes(raw)).decode("utf-8")
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
    ]


def _normalize_bp_indices(best_indices: list[int]) -> list[int]:
    normalized: list[int] = []
    for index in best_indices:
        if index < 1 or index > 200:
            raise ValueError("BP 序号必须在 1-200 之间")
        if index not in normalized:
            normalized.append(index)
    if not normalized:
        raise ValueError("至少需要一个 BP 序号")
    if len(normalized) > 20:
        raise ValueError("单次最多比较 20 个 BP")
    return normalized


def _score_to_bp_summary(score: UnifiedScore, bp_index: int | None = None) -> dict[str, Any]:
    beatmap = score.beatmap
    statistics: dict[str, Any] = {}
    if score.statistics:
        if hasattr(score.statistics, "model_dump"):
            statistics = score.statistics.model_dump(exclude_none=True)
        else:
            statistics = score.statistics.dict(exclude_none=True)
    summary: dict[str, Any] = {
        "beatmap": {
            "id": beatmap.id if beatmap else None,
            "set_id": beatmap.set_id if beatmap else None,
            "artist": beatmap.artist if beatmap else None,
            "title": beatmap.title if beatmap else None,
            "difficulty": beatmap.version if beatmap else None,
            "mapper": beatmap.creator if beatmap else None,
            "stars": round(beatmap.stars, 2) if beatmap else None,
            "bpm": beatmap.bpm if beatmap else None,
            "length_seconds": beatmap.total_length if beatmap else None,
        },
        "score": {
            "rank": score.rank,
            "pp": round(score.pp, 2) if score.pp is not None else None,
            "accuracy": round(score.accuracy, 4),
            "combo": score.max_combo,
            "miss": statistics.get("miss", 0),
            "mods": [mod.acronym for mod in score.mods if mod.acronym != "CL"] or ["NM"],
            "total_score": score.total_score,
            "played_at": score.ended_at.isoformat(),
            "client": score.score_version,
            "statistics": statistics,
        },
    }
    if bp_index is not None:
        summary["bp_index"] = bp_index
    return summary


def _compact_score_summary(score: UnifiedScore, bp_index: int) -> dict[str, Any]:
    beatmap = score.beatmap
    statistics: dict[str, Any] = {}
    if score.statistics:
        if hasattr(score.statistics, "model_dump"):
            statistics = score.statistics.model_dump(exclude_none=True)
        else:
            statistics = score.statistics.dict(exclude_none=True)
    mods = [mod.acronym for mod in score.mods if mod.acronym != "CL"] or ["NM"]
    if "NC" in mods and "DT" in mods:
        mods.remove("DT")
    ended_at = score.ended_at
    return {
        "index": bp_index,
        "title": beatmap.title if beatmap else None,
        "version": beatmap.version if beatmap else None,
        "stars": round(beatmap.stars, 2) if beatmap else None,
        "rank": score.rank,
        "pp": round(score.pp, 2) if score.pp is not None else None,
        "accuracy": round(score.accuracy, 2),
        "combo": score.max_combo,
        "miss": statistics.get("miss", 0),
        "mods": mods,
        "date": ended_at.strftime("%Y.%m.%d") if ended_at is not None else None,
    }


def _recommend_item_summary(item: RecommendItem) -> dict[str, Any]:
    return {
        "title": item.title,
        "stars": round(item.stars, 2),
        "mod": item.mod_str,
        "pred_pp": round(item.pred_pp, 2),
        "pred_acc": round(item.pred_acc, 2),
        "map_id": item.map_id,
        "url": item.url,
    }


def _recommend_to_summary(data: RecommendData) -> dict[str, Any]:
    return {
        "mode": data.mode,
        "target": data.target,
        "recommendations": [_recommend_item_summary(item) for item in (data.recommendations or [])][:10],
        "sections": [
            {
                "title": section.title,
                "count": len(section.items),
                "top": [_recommend_item_summary(item) for item in section.items[:3]],
            }
            for section in (data.sections or [])
        ],
    }


def _bpa_to_summary(data: dict[str, Any]) -> dict[str, Any]:
    rank_distribution: list[dict[str, Any]] = []
    for series in data.get("star_scatter") or []:
        points = series.get("data") or []
        if not points:
            continue
        stars = [point[0] for point in points]
        pps = [point[1] for point in points]
        rank_distribution.append(
            {
                "rank": series.get("name"),
                "count": len(points),
                "avg_stars": round(sum(stars) / len(stars), 2),
                "avg_pp": round(sum(pps) / len(pps), 1),
            }
        )
    return {
        "stats": data.get("stats") or {},
        "rank_distribution": rank_distribution,
        "mod_pp_contribution": data.get("mod_pp_ls") or [],
        "top_mappers": data.get("mapper_pp_ls") or [],
    }


def _history_to_summary(points: list[tuple[float, str, int]]) -> dict[str, Any]:
    pp_ls = [point[0] for point in points]
    date_ls = [point[1] for point in points]
    rank_ls = [point[2] for point in points]
    return {
        "points": len(points),
        "span": {"from": date_ls[0], "to": date_ls[-1]},
        "pp": {
            "first": round(pp_ls[0], 2),
            "last": round(pp_ls[-1], 2),
            "max": round(max(pp_ls), 2),
            "min": round(min(pp_ls), 2),
            "change": round(pp_ls[-1] - pp_ls[0], 2),
        },
        "rank": {
            "first": rank_ls[0],
            "last": rank_ls[-1],
            "best": min(rank_ls),
            "delta": rank_ls[-1] - rank_ls[0],
            "gain": rank_ls[0] - rank_ls[-1],
        },
        "recent": [{"date": date, "pp": round(pp, 2), "rank": rank} for pp, date, rank in points[-20:]],
    }


def _match_history_game_summary(game: dict[str, Any]) -> dict[str, Any]:
    players = game.get("players") or []
    mvp = None
    if players:
        best = players[0]
        mvp = {
            "name": best["name"],
            "team": best["team"],
            "score": best["score"],
            "accuracy": round(best["accuracy"], 2),
            "mods": best["mods"],
        }
    return {
        "index": game["index"],
        "map": f"{game['title']} [{game['version']}]",
        "stars": round(game["stars"], 2),
        "winner": game["winner"],
        "red_score": game["red_score"],
        "blue_score": game["blue_score"],
        "mvp": mvp,
    }


def _match_history_to_summary(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_id": data["match_id"],
        "title": data["title"],
        "team_type": data["team_type"],
        "red_name": data["red_name"],
        "blue_name": data["blue_name"],
        "red_wins": data["red_wins"],
        "blue_wins": data["blue_wins"],
        "game_count": data["game_count"],
        "player_count": data["player_count"],
        "team_size": data["team_size"],
        "duration": data["duration"],
        "complete": data["complete"],
        "games": [_match_history_game_summary(game) for game in (data.get("games") or [])[:15]],
    }


def _match_player_summary(player: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "rank": player["rank"],
        "name": player["name"],
        "team": player.get("team"),
        "rating": round(player["rating"], 2),
        "total_score": player["total_score"],
        "average_score": player["average_score"],
        "played": player.get("played"),
    }
    if player.get("wins") is not None:
        summary["wins"] = player["wins"]
        summary["losses"] = player["losses"]
    if player.get("win_rate") is not None:
        summary["win_rate"] = round(player["win_rate"] * 100, 2)
    if "top1_rate" in player:
        summary["top1_rate"] = round(player["top1_rate"] * 100, 2)
    return summary


def _match_rating_to_summary(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_id": data["match_id"],
        "title": data["title"],
        "team_type": data["team_type"],
        "algorithm": data["algorithm"],
        "time_range": data["time_range"],
        "game_count": data["game_count"],
        "player_count": data["player_count"],
        "team_size": data["team_size"],
        "average_rating": round(data["average_rating"], 2),
        "red_name": data["red_name"],
        "blue_name": data["blue_name"],
        "red_wins": data["red_wins"],
        "blue_wins": data["blue_wins"],
        "mvp": _match_player_summary(data["mvp"]),
        "players": [_match_player_summary(player) for player in data["players"]],
    }


def _info_to_summary(info: UnifiedUser) -> dict[str, Any]:
    statistics = info.statistics
    grade_counts = statistics.grade_counts if statistics else None
    return {
        "id": info.id,
        "username": info.username,
        "country_code": info.country_code,
        "is_supporter": bool(info.is_supporter),
        "follower_count": info.follower_count,
        "join_date": info.join_date,
        "achievement_count": len(info.user_achievements or []),
        "badges": [
            {
                "description": badge.description,
                "awarded_at": badge.awarded_at,
                "url": badge.url,
            }
            for badge in (info.badges or [])[:8]
        ],
        "statistics": {
            "pp": round(statistics.pp, 2) if statistics else None,
            "global_rank": statistics.global_rank if statistics else None,
            "country_rank": statistics.country_rank if statistics else None,
            "accuracy": round(statistics.hit_accuracy, 2) if statistics else None,
            "play_count": statistics.play_count if statistics else None,
            "total_hits": statistics.total_hits if statistics else None,
            "ranked_score": statistics.ranked_score if statistics else None,
            "total_score": statistics.total_score if statistics else None,
            "maximum_combo": statistics.maximum_combo if statistics else None,
            "play_time": statistics.play_time if statistics else None,
            "grade_counts": (
                {
                    "ssh": grade_counts.ssh,
                    "ss": grade_counts.ss,
                    "sh": grade_counts.sh,
                    "s": grade_counts.s,
                    "a": grade_counts.a,
                }
                if grade_counts
                else None
            ),
        },
    }


def _bp_tool_result(
    status: Literal["sent", "already_sent", "ok", "expired", "failed"],
    message: str,
    *,
    player: str | None = None,
    mode: str | None = None,
    purpose: Literal["view", "analyze"] | None = None,
    scores: list[dict[str, Any]] | None = None,
) -> str:
    result: dict[str, Any] = {"status": status, "message": message}
    if player is not None:
        result["player"] = player
    if mode is not None:
        result["mode"] = mode
    if purpose is not None:
        result["purpose"] = purpose
        result["next_action"] = "finish" if purpose == "view" else "reply_with_analysis"
    if scores is not None:
        result["scores"] = scores
    return json.dumps(result, ensure_ascii=False)


async def _is_context_request_active(ctx: AgentToolContext) -> bool:
    if ctx.request_id is None:
        return True
    return await is_request_active(ctx.session_id, ctx.request_id)


async def _query_bp_scores(
    user: ResolvedOsuUser,
    mode: str,
    mods: list[str],
    source: str,
    is_lazer: bool,
    best_indices: list[int],
) -> list[dict[str, Any]]:
    indices = _normalize_bp_indices(best_indices)
    scores = await get_user_scores(
        user.user_id,
        NGM[mode],
        "best",
        source=source,
        legacy_only=not is_lazer,
        limit=200 if mods else max(indices),
    )
    filtered_indices = get_mods_list(scores, mods)
    if len(filtered_indices) < max(indices):
        raise NetworkError("未查询到指定的 BP 成绩")

    summaries: list[dict[str, Any]] = []
    for bp_index in indices:
        score = scores[filtered_indices[bp_index - 1]]
        if source == "osu":
            score = cal_score_info(is_lazer, score, source)
        summaries.append(_score_to_bp_summary(score, bp_index))
    return summaries


def _strip_medal_html(text: str) -> str:
    table_match = re.search(r"<table[^>]*>(.*?)</table>", text, re.DOTALL)
    if table_match:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.DOTALL)
        result = ""
        for row in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
            result += " ".join(re.sub(r"<[^>]*>", "", cell) for cell in cells) + "\n"
        text = re.sub(r"<table[^>]*>.*?</table>", result, text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    return re.sub(r"<[^>]+>", "", text)


def _beatmap_search_candidates(
    beatmapsets: list[dict[str, Any]],
    mode: str | None,
    limit: int,
    query: str | None = None,
) -> list[dict[str, Any]]:
    normalized_query = re.sub(r"\W+", "", (query or "").casefold())

    def text_rank(value: Any) -> int:
        normalized = re.sub(r"\W+", "", str(value or "").casefold())
        if not normalized_query:
            return 3
        if normalized == normalized_query:
            return 0
        if normalized_query in normalized:
            return 1
        return 3

    def set_rank(beatmapset: dict[str, Any]) -> int:
        values = [
            beatmapset.get("title"),
            beatmapset.get("title_unicode"),
            beatmapset.get("artist"),
            beatmapset.get("artist_unicode"),
            beatmapset.get("creator"),
            *(beatmap.get("version") for beatmap in beatmapset.get("beatmaps") or []),
        ]
        return min((text_rank(value) for value in values), default=3)

    target_mode = int(mode) if mode is not None else None
    candidates: list[dict[str, Any]] = []
    for beatmapset in sorted(beatmapsets, key=set_rank):
        beatmaps = beatmapset.get("beatmaps") or []
        # 先匹配明确给出的难度名，再优先目标原生模式；std 谱面仍保留用于转谱查询。
        beatmaps = sorted(
            beatmaps,
            key=lambda item: (
                target_mode is not None and int(item.get("mode_int", 0)) != target_mode,
                target_mode is not None and int(item.get("mode_int", 0)) != 0,
                text_rank(item.get("version")),
            ),
        )
        for beatmap in beatmaps:
            native_mode = int(beatmap.get("mode_int", 0))
            if target_mode is not None and native_mode not in {0, target_mode}:
                continue
            candidates.append(
                {
                    "beatmap_id": beatmap.get("id"),
                    "beatmapset_id": beatmapset.get("id"),
                    "artist": beatmapset.get("artist"),
                    "title": beatmapset.get("title"),
                    "difficulty": beatmap.get("version"),
                    "mapper": beatmapset.get("creator"),
                    "native_mode_id": native_mode,
                    "native_mode": NGM.get(str(native_mode), str(native_mode)),
                    "stars": round(float(beatmap.get("difficulty_rating") or 0), 2),
                    "checksum": beatmap.get("checksum"),
                    "total_length": int(beatmap.get("total_length") or 0),
                    "bpm": float(beatmap.get("bpm") or beatmapset.get("bpm") or 0),
                    "cs": float(beatmap.get("cs") or 0),
                    "od": float(beatmap.get("accuracy") or 0),
                    "ar": float(beatmap.get("ar") or 0),
                    "hp": float(beatmap.get("drain") or 0),
                    "mapper_id": beatmap.get("user_id") or beatmapset.get("user_id"),
                    "status": beatmapset.get("status"),
                    "url": f"https://osu.ppy.sh/b/{beatmap.get('id')}",
                }
            )
            if len(candidates) >= limit:
                return candidates
    return candidates


def _named_score_summary(score_data: dict[str, Any]) -> dict[str, Any]:
    score = score_data["score"]
    statistics = score.get("statistics") or {}
    mods = [mod.get("acronym", "") if isinstance(mod, dict) else str(mod) for mod in score.get("mods") or []]
    return {
        "rank": score.get("rank"),
        "pp": round(float(score["pp"]), 2) if score.get("pp") is not None else None,
        "accuracy": round(float(score.get("accuracy") or 0) * 100, 4),
        "combo": score.get("max_combo"),
        "miss": statistics.get("miss", 0),
        "mods": [mod for mod in mods if mod] or ["NM"],
        "total_score": score.get("total_score"),
        "played_at": score.get("ended_at"),
        "client": "stable" if score.get("legacy_score_id") else "lazer",
        "global_position": score_data.get("position"),
    }


def _named_score_analysis_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "beatmap_id": result.get("beatmap_id"),
        "artist": result.get("artist"),
        "title": result.get("title"),
        "difficulty": result.get("difficulty"),
        "mapper": result.get("mapper"),
        "stars": result.get("stars"),
        "score": result.get("score"),
    }


def _named_score_to_unified(score_data: dict[str, Any], candidate: dict[str, Any], ruleset_id: int) -> UnifiedScore:
    score = score_data["score"]
    ended_at = datetime.datetime.fromisoformat(
        str(score.get("ended_at") or datetime.datetime.now().isoformat()).replace("Z", "+00:00")
    )
    if ended_at.tzinfo is not None:
        ended_at = ended_at.astimezone(datetime.timezone(datetime.timedelta(hours=8))).replace(tzinfo=None)
    mods = [mod if isinstance(mod, dict) else {"acronym": str(mod)} for mod in score.get("mods") or []]
    native_mode = int(candidate.get("native_mode_id") or 0)
    return UnifiedScore(
        mods=[Mod(**mod) for mod in mods],
        ruleset_id=ruleset_id,
        rank=str(score.get("rank") or "F"),
        accuracy=float(score.get("accuracy") or 0) * 100,
        total_score=int(score.get("total_score") or 0),
        legacy_total_score=score.get("legacy_total_score"),
        ended_at=ended_at,
        max_combo=int(score.get("max_combo") or 0),
        statistics=NewStatistics(**(score.get("statistics") or {})),
        passed=bool(score.get("passed", True)),
        pp=score.get("pp"),
        score_version="stable" if score.get("legacy_score_id") is not None else "lazer",
        beatmap=UnifiedBeatmap(
            id=int(candidate["beatmap_id"]),
            set_id=int(candidate["beatmapset_id"]),
            artist=str(candidate.get("artist") or ""),
            title=str(candidate.get("title") or ""),
            version=str(candidate.get("difficulty") or ""),
            creator=str(candidate.get("mapper") or ""),
            total_length=int(candidate.get("total_length") or 0),
            mode=native_mode,
            bpm=float(candidate.get("bpm") or 0),
            cs=float(candidate.get("cs") or 0),
            od=float(candidate.get("od") or 0),
            ar=float(candidate.get("ar") or 0),
            hp=float(candidate.get("hp") or 0),
            stars=float(candidate.get("stars") or 0),
            checksum=candidate.get("checksum"),
            user_id=candidate.get("mapper_id"),
            convert=native_mode != ruleset_id,
        ),
    )


async def _draw_preview(map_id: str, mode: str, mods: str, full: bool) -> tuple[bytes | BytesIO | Path, str | None]:
    if not map_id.isdigit():
        raise ValueError("map_id 必须是数字")
    if mode not in {"0", "1", "2", "3"}:
        raise ValueError("preview 仅支持 0=std, 1=taiko, 2=ctb/fruits, 3=mania")
    data = await osu_api("map", map_id=int(map_id))
    beatmapset_id = data["beatmapset_id"]
    mod_list = mods2list(mods) if mods else []

    if "GIF" in "".join(mod.upper() for mod in mod_list):
        media = (
            await draw_full_osu_preview(int(map_id), beatmapset_id)
            if full
            else await draw_osu_preview(int(map_id), beatmapset_id)
        )
        extra_text = (
            f"点击预览：\nhttps://beatmap.try-z.net/?b={map_id}\nhttps://beatmap.try-z.net/dev/?b={map_id}"
            if mode == "0"
            else None
        )
        return media, extra_text
    if mode == "3":
        osu = await download_osu(beatmapset_id, int(map_id))
        return await generate_preview_pic(osu, full), None
    if mode == "2":
        return await draw_cath_preview(int(map_id), beatmapset_id, mod_list), None
    if mode == "1":
        osu = await download_osu(beatmapset_id, int(map_id))
        return map_to_image(parse_map(osu)), None
    image = await draw_osu_preview(int(map_id), beatmapset_id)
    return image, f"点击预览：\nhttps://beatmap.try-z.net/?b={map_id}\nhttps://beatmap.try-z.net/dev/?b={map_id}"


@register_agent_tool
def build_osu_agent_tools(ctx: AgentToolContext) -> AgentToolBundle:
    bp_delivery_lock = asyncio.Lock()
    delivered_bp_keys: set[tuple[Any, ...]] = set()
    bp_artifact_cache: dict[tuple[Any, ...], tuple[bytes | BytesIO, dict[str, Any]]] = {}
    bp_list_cache: dict[tuple[Any, ...], list[UnifiedScore]] = {}

    async def fetch_bp_list(
        user: ResolvedOsuUser,
        mode: str,
        mod_list: list[str],
        source: str,
        is_lazer: bool,
    ) -> list[UnifiedScore]:
        cache_key = (user.user_id, source, mode, is_lazer, tuple(sorted(mod_list)))
        cached = bp_list_cache.get(cache_key)
        if cached is not None:
            return cached
        scores = await get_user_scores(
            user.user_id,
            NGM[mode],
            "best",
            source=source,
            legacy_only=not is_lazer,
        )
        if source == "osu":
            scores = [cal_score_info(is_lazer, score, source) for score in scores]
        bp_list_cache[cache_key] = scores
        return scores

    async def deliver_bp_once(
        delivery_key: tuple[Any, ...], image: bytes | BytesIO
    ) -> Literal["sent", "already_sent", "expired"]:
        async with bp_delivery_lock:
            if delivery_key in delivered_bp_keys:
                return "already_sent"
            if not await _is_context_request_active(ctx):
                return "expired"
            await _send_image(ctx, image)
            delivered_bp_keys.add(delivery_key)
            return "sent"

    @tool("get_osubot_command_help")
    async def get_osubot_command_help(topic: str = "overview") -> str:
        """
        查询 OSUBot 的手动聊天指令、格式、简称和示例，不执行成绩查询。
        topic 可用 overview、bind、mode、score、map、profile、game、sb、all，也可传中文主题。
        """
        return get_command_help(topic)

    @tool("send_osu_user_info")
    async def send_osu_user_info(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        day: int = 0,
        source: str = "osu",
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送 osu 玩家信息图。
        username 不填时使用当前用户或被 @ 群友绑定的 osu 账号。
        mode: 0=std, 1=taiko, 2=ctb/fruits, 3=mania。source: osu 或 ppysb。
        """
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            drawn = await draw_info(user.user_id, NGM[mode], max(day, 0), source, return_info=True)
            data, info = drawn
            await _send_image(ctx, data)
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 {user.name} 的 osu 信息图，并返回结构化资料。",
                    "player": user.name,
                    "mode": NGM[mode],
                    "info": _info_to_summary(info),
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, data, include_image_for_analysis)
        except NetworkError as e:
            return f"查询 osu 玩家信息失败: {e}"
        except Exception as e:
            return f"发送 osu 玩家信息失败: {e}"

    @tool("send_osu_bp")
    async def send_osu_bp(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        best: int = 1,
        mode: str | None = None,
        mods: str = "",
        source: str = "osu",
        is_lazer: bool | None = None,
        purpose: BpPurposeArg = "view",
    ) -> str:
        """
        查询并发送 osu 玩家指定 BP 成绩图。
        best 为 BP 序号，范围 1-200；mods 可填 HDHR、DT、HD 等。
        purpose=view 只展示查询结果；purpose=analyze 会同时返回结构化成绩供分析。
        同一请求使用相同参数重复调用时不会重复发送图片。
        """
        try:
            if best < 1 or best > 200:
                return _bp_tool_result("failed", "best 必须在 1-200 之间")
            if not await _is_context_request_active(ctx):
                return _bp_tool_result("expired", "请求已过期，已取消查询和发送。")
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            mod_list = mods2list(mods) if mods else []
            delivery_key = (
                user.user_id,
                source,
                mode,
                is_lazer,
                tuple(sorted(mod_list)),
                best,
            )

            artifact = bp_artifact_cache.get(delivery_key)
            if artifact is None:
                data, score = await draw_score(
                    "bp",
                    user.user_id,
                    is_lazer,
                    NGM[mode],
                    mod_list,
                    [],
                    source,
                    best=best,
                    return_score=True,
                )
                summary = _score_to_bp_summary(score, best)
                artifact = (data, summary)
                bp_artifact_cache[delivery_key] = artifact

            data, summary = artifact
            delivery_status = await deliver_bp_once(delivery_key, data)
            if delivery_status == "expired":
                return _bp_tool_result("expired", "请求已过期，已取消发送。")
            message = (
                f"已发送 {user.name} 的 BP{best}。"
                if delivery_status == "sent"
                else f"{user.name} 的 BP{best} 已在本轮发送过，不再重复发送。"
            )
            return _bp_tool_result(
                delivery_status,
                message,
                player=user.name,
                mode=NGM[mode],
                purpose=purpose,
                scores=[summary] if purpose == "analyze" else None,
            )
        except NetworkError as e:
            return _bp_tool_result("failed", f"查询 BP 失败: {e}")
        except Exception as e:
            return _bp_tool_result("failed", f"发送 BP 失败: {e}")

    @tool("get_osu_bp_data")
    async def get_osu_bp_data(
        best_indices: list[int],
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        mods: str = "",
        source: str = "osu",
        is_lazer: bool | None = None,
    ) -> str:
        """
        读取一个或多个 BP 的结构化成绩，不发送图片。
        仅用于比较多个 BP 或进行复杂分析；普通查询应使用 send_osu_bp。
        best_indices 为 1-200 范围内的 BP 序号，一次建议不超过 10 个（超过会因结果过长被截断丢失中间数据）。
        """
        try:
            if not await _is_context_request_active(ctx):
                return _bp_tool_result("expired", "请求已过期，已取消查询。")
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            summaries = await _query_bp_scores(
                user,
                mode,
                mods2list(mods) if mods else [],
                source,
                is_lazer,
                best_indices,
            )
            return _bp_tool_result(
                "ok",
                f"已读取 {user.name} 的 {len(summaries)} 条 BP 数据，未发送图片。",
                player=user.name,
                mode=NGM[mode],
                scores=summaries,
            )
        except (NetworkError, ValueError) as e:
            return _bp_tool_result("failed", f"查询 BP 数据失败: {e}")
        except Exception as e:
            return _bp_tool_result("failed", f"读取 BP 数据失败: {e}")

    @tool("get_osu_bp_range")
    async def get_osu_bp_range(
        range_text: str,
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        mods: str = "",
        source: str = "osu",
        is_lazer: bool | None = None,
    ) -> str:
        """
        按范围分页读取玩家 BP 的结构化数据，每次最多 20 条，不发送图片。
        用于分析整体 BP 构成/实力/吃分分布；先从 1-20 开始，返回 has_more=true 时按 next_start 继续读取。
        range_text 类似 1-20，宽度不能超过 20。
        """
        try:
            if not await _is_context_request_active(ctx):
                return _bp_tool_result("expired", "请求已过期，已取消查询。")
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            mod_list = mods2list(mods) if mods else []
            low, high = _normalize_range(range_text, default="1-20")
            if high - low + 1 > 20:
                return _bp_tool_result("failed", "get_osu_bp_range 每次最多读取 20 条，请使用类似 1-20 的范围。")
            scores = await fetch_bp_list(user, mode, mod_list, source, is_lazer)
            filtered_indices = get_mods_list(scores, mod_list)
            if not filtered_indices:
                return _bp_tool_result("failed", "未查询到指定的 BP 成绩")
            total = len(filtered_indices)
            if low > total:
                return _bp_tool_result("failed", f"BP {low} 超出该玩家的 BP 总数 {total}")
            page_indices = filtered_indices[low - 1 : high]
            if not page_indices:
                return _bp_tool_result("failed", "未查询到游玩记录")
            shown_high = min(high, total)
            compact = [
                _compact_score_summary(scores[score_index], position)
                for position, score_index in enumerate(page_indices, start=low)
            ]
            result: dict[str, Any] = {
                "status": "ok",
                "message": f"已读取 {user.name} 的 BP {low}-{shown_high} 数据，未发送图片。",
                "player": user.name,
                "mode": NGM[mode],
                "range": [low, shown_high],
                "total": total,
                "has_more": high < total,
                "scores": compact,
            }
            if high < total:
                result["next_start"] = high + 1
            return json.dumps(result, ensure_ascii=False)
        except (NetworkError, ValueError) as e:
            return _bp_tool_result("failed", f"查询 BP 数据失败: {e}")
        except Exception as e:
            return _bp_tool_result("failed", f"读取 BP 数据失败: {e}")

    @tool("send_osu_bp_list")
    async def send_osu_bp_list(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        range_text: str | None = None,
        mode: str | None = None,
        mods: str = "",
        filters: BpFiltersArg = "",
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送 osu 玩家 BP 列表图。
        range_text 是 BP 范围，例如 1-20；不筛选时默认 1-30，筛选时默认搜索 1-200。
        mods 是必须包含的 Mods，例如 HDHR；filters 使用 /bl 相同的筛选语法，多个条件为 AND。
        常用 filters：300pp+、98a+、5-7*、7d、24h、fc、nofc、-DT、=HDHR。
        完整字段支持 pp/acc/stars/miss/combo/bpm/length/mapper/title/version/rank/client/date/days/speed/mods 等；
        可简写为 p/a/s/m/c/b/len/mp/t/v/r/cl/sp/mod，文本有空格时使用引号。
        """
        try:
            source = _normalize_source(source)
            search_conditions, invalid_filter = parse_bp_filter_text(filters)
            if invalid_filter:
                return f"无法识别 BP 筛选条件: {invalid_filter}"
            default_range = "1-200" if search_conditions else "1-30"
            low, high = _normalize_range(range_text, default=default_range)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            mod_list = mods2list(mods) if mods else []
            scores, selected = await select_bp_scores(
                "bp",
                user.user_id,
                is_lazer,
                NGM[mode],
                mod_list,
                low,
                high,
                0,
                search_conditions,
                source,
            )
            if len(selected) == 1:
                data, score = await draw_selected_score(
                    selected[0],
                    user.user_id,
                    is_lazer,
                    NGM[mode],
                    source,
                )
                await _send_image(ctx, data)
                text = json.dumps(
                    {
                        "status": "sent",
                        "message": f"筛选后只有一条成绩，已发送 {user.name} 的单张成绩图，并返回结构化成绩。",
                        "player": user.name,
                        "mode": NGM[mode],
                        "scores": [_score_to_bp_summary(score)],
                    },
                    ensure_ascii=False,
                )
                return _image_tool_result(text, data, include_image_for_analysis)
            delivery_key = (
                user.user_id,
                source,
                mode,
                is_lazer,
                tuple(sorted(mod_list)),
                "bp_list",
                low,
                high,
                filters,
            )
            if delivery_key in delivered_bp_keys:
                return f"{user.name} 的 bp{low}-{high} 已在本轮发送过，不再重复发送。"
            data = await draw_pfm("bp", user.user_id, scores, selected, NGM[mode], source, low, high, 0)
            delivery_status = await deliver_bp_once(delivery_key, data)
            if delivery_status == "expired":
                return "请求已过期，已取消发送。"
            if delivery_status == "already_sent":
                return f"{user.name} 的 bp{low}-{high} 已在本轮发送过，不再重复发送。"
            return _image_tool_result(
                f"已发送 {user.name} 的 bp{low}-{high}"
                f"{'（筛选：' + filters + '）' if filters else ''}。图片中包含 bp 列表，可用于分析成绩分布和整体表现。",
                data,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询 bp 列表失败: {e}"
        except Exception as e:
            return f"发送 bp 列表失败: {e}"

    @tool("send_osu_firsts")
    async def send_osu_firsts(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        range_text: str | None = None,
        mode: str | None = None,
        mods: str = "",
        filters: BpFiltersArg = "",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送 osu 玩家在全球排行榜取得第一名的成绩列表（firsts/榜一）。
        range_text 是榜一记录序号或范围，例如 5 或 1-20；不筛选时默认 1-30，筛选时默认搜索 1-200。
        mods 是必须包含的 Mods；filters 与 BP 列表使用相同的筛选语法。仅支持 osu! 官网。
        """
        try:
            source = "osu"
            search_conditions, invalid_filter = parse_bp_filter_text(filters)
            if invalid_filter:
                return f"无法识别第一名成绩筛选条件: {invalid_filter}"
            default_range = "1-200" if search_conditions else "1-30"
            low, high = _normalize_firsts_range(range_text, default=default_range)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            mod_list = mods2list(mods) if mods else []
            scores, selected = await select_bp_scores(
                "firsts",
                user.user_id,
                is_lazer,
                NGM[mode],
                mod_list,
                low,
                high,
                0,
                search_conditions,
                source,
            )
            delivery_key = (
                user.user_id,
                source,
                mode,
                is_lazer,
                tuple(sorted(mod_list)),
                "firsts_list",
                low,
                high,
                filters,
            )
            if delivery_key in delivered_bp_keys:
                return f"{user.name} 的榜一 {low}-{high} 已在本轮发送过，不再重复发送。"
            data = await draw_pfm("firsts", user.user_id, scores, selected, NGM[mode], source, low, high, 0)
            delivery_status = await deliver_bp_once(delivery_key, data)
            if delivery_status == "expired":
                return "请求已过期，已取消发送。"
            if delivery_status == "already_sent":
                return f"{user.name} 的榜一 {low}-{high} 已在本轮发送过，不再重复发送。"
            return _image_tool_result(
                f"已发送 {user.name} 的第一名成绩 {low}-{high}{'（筛选：' + filters + '）' if filters else ''}。",
                data,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询第一名成绩失败: {e}"
        except Exception as e:
            return f"发送第一名成绩失败: {e}"

    @tool("send_osu_recent_or_pr")
    async def send_osu_recent_or_pr(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        kind: str = "recent",
        index: int = 1,
        mode: str | None = None,
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送最近成绩或最近 best 成绩图。kind 为 recent 或 pr；index 表示第几条，默认 1。
        """
        try:
            if index < 1:
                return "index 必须大于等于 1"
            score_type = "pr" if kind.lower() == "pr" else "recent"
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            data, score = await draw_score(
                score_type,
                user.user_id,
                is_lazer,
                NGM[mode],
                [],
                [],
                source,
                index,
                return_score=True,
            )
            await _send_image(ctx, data)
            label = "最近 best" if score_type == "pr" else "最近"
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 {user.name} 的第 {index} 个{label}成绩，并返回结构化成绩。",
                    "player": user.name,
                    "mode": NGM[mode],
                    "scores": [_score_to_bp_summary(score)],
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, data, include_image_for_analysis)
        except NetworkError as e:
            return f"查询最近成绩失败: {e}"
        except Exception as e:
            return f"发送最近成绩失败: {e}"

    @tool("send_osu_score")
    async def send_osu_score(
        beatmap_id: str,
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        mods: str = "",
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送玩家在指定 beatmap 上的成绩图。beatmap_id 是谱面 ID。
        """
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            data, score = await get_score_data(
                user.user_id,
                is_lazer,
                NGM[mode],
                mods2list(mods) if mods else [],
                int(beatmap_id),
                source,
                return_score=True,
            )
            await _send_image(ctx, data)
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 {user.name} 在谱面 {beatmap_id} 上的成绩，并返回结构化成绩。",
                    "player": user.name,
                    "mode": NGM[mode],
                    "scores": [_score_to_bp_summary(score)],
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, data, include_image_for_analysis)
        except NetworkError as e:
            return f"查询谱面成绩失败: {e}"
        except Exception as e:
            return f"发送谱面成绩失败: {e}"

    @tool("search_osu_beatmaps")
    async def search_osu_beatmaps(query: str, mode: str | None = None, limit: int = 8) -> str:
        """
        按歌曲名、艺术家、谱师或难度名搜索 osu 谱面，返回可供其他工具使用的 beatmap_id 候选。
        只搜索，不发送图片。mode: 0=std、1=taiko、2=ctb、3=mania；省略则搜索全部模式。
        """
        try:
            query = query.strip()
            if not query:
                raise ValueError("query 不能为空")
            if not 1 <= limit <= 20:
                raise ValueError("limit 必须在 1-20 之间")
            normalized_mode = _normalize_mode(mode, "osu") if mode is not None else None
            candidates = _beatmap_search_candidates(
                await search_beatmapsets(query),
                normalized_mode,
                limit,
                query,
            )
            if not candidates:
                return json.dumps(
                    {"status": "not_found", "query": query, "candidates": []},
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "status": "ok",
                    "query": query,
                    "mode": NGM.get(normalized_mode) if normalized_mode is not None else None,
                    "candidates": candidates,
                    "next_action": "候选明确时将 beatmap_id 传给目标工具；候选不明确时先让用户选择，禁止猜测。",
                },
                ensure_ascii=False,
            )
        except NetworkError as e:
            return f"搜索谱面失败: {e}"
        except Exception as e:
            return f"搜索谱面失败: {e}"

    @tool("get_osu_scores_by_map_name")
    async def get_osu_scores_by_map_name(
        query: str,
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        is_lazer: bool | None = None,
        limit: int = 20,
        purpose: BpPurposeArg = "view",
    ) -> str:
        """
        按谱面名称搜索，并批量查询玩家在候选难度上的最佳成绩。
        只有一个难度有成绩时直接发送成绩图；多个难度有成绩时发送图片列表。
        purpose=view 只展示查询结果；purpose=analyze 会同时返回紧凑的结构化成绩供分析。
        适合“我在 xxx 图打了多少”且用户没有提供 beatmap ID 的问题。
        """
        try:
            query = query.strip()
            if not query:
                raise ValueError("query 不能为空")
            if not 1 <= limit <= 20:
                raise ValueError("limit 必须在 1-20 之间")
            user = await _resolve_osu_user(ctx, username, "osu", target_user_id)
            resolved_mode = _resolve_mode(mode, user, "osu")
            is_lazer = _resolve_is_lazer(is_lazer)
            candidates = _beatmap_search_candidates(
                await search_beatmapsets(query),
                resolved_mode,
                limit,
                query,
            )
            if not candidates:
                return json.dumps(
                    {"status": "not_found", "query": query, "player": user.name, "results": []},
                    ensure_ascii=False,
                )

            semaphore = asyncio.Semaphore(3)

            async def query_candidate(
                candidate: dict[str, Any],
            ) -> tuple[dict[str, Any], UnifiedScore | None]:
                result = dict(candidate)
                native_mode = int(candidate["native_mode_id"])
                score_mode_id = normalize_map_mode(resolved_mode, native_mode)
                score_mode = NGM[score_mode_id]
                try:
                    async with semaphore:
                        score_data = await osu_api(
                            "best_score",
                            user.user_id,
                            score_mode,
                            int(candidate["beatmap_id"]),
                            legacy_only=int(not is_lazer),
                        )
                    result["score"] = _named_score_summary(score_data)
                    unified_score = _named_score_to_unified(score_data, candidate, int(score_mode_id))
                except NetworkError as e:
                    unified_score = None
                    if "未找到" in str(e):
                        result["score"] = None
                    else:
                        result["score"] = None
                        result["query_error"] = str(e)
                return result, unified_score

            queried = await asyncio.gather(*(query_candidate(candidate) for candidate in candidates))
            results = [result for result, _ in queried]
            played = [(result, score) for result, score in queried if score is not None]
            has_query_error = any("query_error" in result for result in results)
            if len(played) == 1 and not has_query_error:
                selected, _ = played[0]
                image = await get_score_data(
                    user.user_id,
                    is_lazer,
                    NGM[resolved_mode],
                    [],
                    int(selected["beatmap_id"]),
                    "osu",
                )
                await _send_image(ctx, image)
                return json.dumps(
                    {
                        "status": "sent",
                        "message": f"已发送 {user.name} 在唯一有成绩的难度上的成绩图。",
                        "player": user.name,
                        "mode": NGM[resolved_mode],
                        "purpose": purpose,
                        "selected": selected,
                        "scores": ([_named_score_analysis_summary(selected)] if purpose == "analyze" else None),
                        "next_action": "reply_with_analysis" if purpose == "analyze" else "finish",
                    },
                    ensure_ascii=False,
                )
            query_error_count = sum("query_error" in result for result in results)
            if played:
                played_scores = [score for _, score in played]
                image = await draw_pfm(
                    "map_scores",
                    user.user_id,
                    played_scores,
                    played_scores,
                    NGM[resolved_mode],
                    "osu",
                )
                await _send_image(ctx, image)
                message = "已发送谱面成绩图片列表。"
            else:
                text_message = (
                    f"{user.name} · {NGM[resolved_mode]} · {query}\n已检查 {len(results)} 个相关难度，未查询到成绩。"
                )
                if query_error_count:
                    text_message += f"\n另有 {query_error_count} 个难度查询失败，请稍后重试。"
                await _send_text(ctx, text_message)
                message = "未查到成绩，已发送查询结果。"
            return json.dumps(
                {
                    "status": "sent",
                    "message": message,
                    "player": user.name,
                    "mode": NGM[resolved_mode],
                    "purpose": purpose,
                    "played_count": len(played),
                    "scores": (
                        [_named_score_analysis_summary(result) for result, _ in played]
                        if purpose == "analyze"
                        else None
                    ),
                    "next_action": ("reply_with_analysis" if purpose == "analyze" and played else "finish"),
                },
                ensure_ascii=False,
            )
        except NetworkError as e:
            return f"按名称查询谱面成绩失败: {e}"
        except Exception as e:
            return f"按名称查询谱面成绩失败: {e}"

    @tool("send_osu_history")
    async def send_osu_history(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        day: int = 0,
        source: str = "osu",
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送玩家 pp/rank 历史曲线图。day 为查询最近多少天，0 表示全部。"""
        try:
            source = _normalize_source(source)
            if source != "osu":
                return "history 暂仅支持 osu 官方服务器"
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            query = select(InfoData).where(InfoData.osu_id == user.user_id, InfoData.osu_mode == int(mode))
            if day > 0:
                query = query.where(InfoData.date >= datetime.date.today() - datetime.timedelta(days=day))
            query = query.order_by(InfoData.date)
            async with get_session() as session:
                data = (await session.scalars(query)).all()

            local_points = [
                (item.pp, str(item.date), item.g_rank) for item in data if item.g_rank is not None and item.g_rank != 0
            ]
            has_local_points = bool(local_points)
            points, used_osutrack = await merge_osutrack_history(user.user_id, int(mode), local_points, day)
            if not points:
                return f"没有找到 {user.name} 的历史数据"
            pp_ls, date_ls, rank_ls = map(list, zip(*points))
            source_label = "本地记录"
            if used_osutrack:
                source_label = "本地记录 + osu!track" if has_local_points else "osu!track"
            image = await draw_history_plot(
                pp_ls,
                date_ls,
                rank_ls,
                f"{user.name} {NGM[mode]} pp/rank history",
                username=user.name,
                mode=NGM[mode],
                user_id=user.user_id,
                source_label=source_label,
            )
            await _send_image(ctx, image)
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 {user.name} 的 {NGM[mode]} pp/rank 历史曲线图，并返回结构化数据。",
                    "player": user.name,
                    "mode": NGM[mode],
                    "history": _history_to_summary(points),
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, image, include_image_for_analysis)
        except Exception as e:
            return f"发送历史曲线失败: {e}"

    @tool("send_osu_bp_analysis")
    async def send_osu_bp_analysis(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送玩家 bp 分析图，展示 bp 长度、mod 贡献和 mapper 贡献。"""
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer)
            score_ls = await get_user_scores(user.user_id, NGM[mode], "best", source, legacy_only=not is_lazer)
            if not score_ls:
                return f"没有找到 {user.name} 的 bp 成绩"

            for score in score_ls:
                if not is_lazer or source == "ppysb":
                    score.mods = [mod for mod in score.mods if mod.acronym != "CL"]
                for mod in score.mods:
                    if not score.beatmap:
                        continue
                    if mod.acronym in {"DT", "NC"}:
                        setattr(score.beatmap, "total_length", score.beatmap.total_length / 1.5)
                    if mod.acronym == "HT":
                        setattr(score.beatmap, "total_length", score.beatmap.total_length / 0.75)

            score_ls = [cal_score_info(is_lazer, score) for score in score_ls]
            data = await build_bpa_data(score_ls, source)
            image = await draw_bpa_plot(
                f"{user.name} {NGM[mode]} 模式",
                username=user.name,
                mode=NGM[mode],
                user_id=user.user_id,
                source=source,
                **data,
            )
            await _send_image(ctx, image)
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 {user.name} 的 {NGM[mode]} bp 分析图，并返回结构化分析数据。",
                    "player": user.name,
                    "mode": NGM[mode],
                    "bpa": _bpa_to_summary(data),
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, image, include_image_for_analysis)
        except NetworkError as e:
            return f"查询 bp 分析失败: {e}"
        except Exception as e:
            return f"发送 bp 分析失败: {e}"

    @tool("send_osu_recommend")
    async def send_osu_recommend(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        mode: str | None = None,
        target: str | None = "mixed",
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送推荐谱面图。
        target 取值规则：普通推荐/综合/好玩且能打用 mixed；吃分/pp/能上分用 farm；难一点/更难/高难/冲分/peak 用 peak；
        练习/风格/值得练/practice/style 用 style；均衡/balanced 用 balanced。
        target_user_id 是 QQ/群用户 ID，不是 osu id；查询当前发言人时不要填写 target_user_id。
        """
        try:
            user = await _resolve_osu_user(ctx, username, "osu", target_user_id)
            mode = _resolve_mode(mode, user, "osu")
            api_task = asyncio.create_task(get_recommend(user.user_id, mode, target))
            done, _ = await asyncio.wait([api_task], timeout=5)
            if not done:
                await UniMessage.text("正在获取推荐谱面，请稍候...").send(target=ctx.send_target)
            recommend_data = await api_task
            if not recommend_data.recommendations:
                return "暂时没有找到可推荐的谱面，已加入更新队列，请明天再来查看推荐吧"
            image = await draw_recommend(recommend_data, user.name, f"https://a.ppy.sh/{user.user_id}")
            await _send_image(ctx, image)
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 {user.name} 的推荐谱面图，并返回结构化推荐数据。",
                    "player": user.name,
                    "mode": NGM[mode],
                    "recommend": _recommend_to_summary(recommend_data),
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, image, include_image_for_analysis)
        except NetworkError as e:
            return f"查询推荐谱面失败: {e}"
        except Exception as e:
            return f"发送推荐谱面失败: {e}"

    @tool("send_osu_profile_url")
    async def send_osu_profile_url(
        username: UsernameArg = None,
        target_user_id: TargetUserIdArg = None,
        source: str = "osu",
    ) -> str:
        """发送玩家 osu 主页链接。"""
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            url = f"https://osu.ppy.sh/u/{user.user_id}" if source == "osu" else f"https://akatsuki.gg/u/{user.user_id}"
            await UniMessage.text(url).send(target=ctx.send_target)
            return f"已发送 {user.name} 的主页链接: {url}"
        except Exception as e:
            return f"发送主页链接失败: {e}"

    @tool("send_osu_match_history")
    async def send_osu_match_history(
        match_id: str,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送 osu match 对局历史图。match_id 为多人房间 ID。"""
        try:
            drawn = await draw_match_history(match_id.strip(), return_data=True)
            image, match_data = drawn
            await _send_image(ctx, image)
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 match {match_id} 对局历史图，并返回结构化对局数据。",
                    "match": _match_history_to_summary(match_data),
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, image, include_image_for_analysis)
        except Exception as e:
            return f"发送 match 历史失败: {e}"

    @tool("send_osu_match_rating")
    async def send_osu_match_rating(
        match_id: str,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送 osu match rating 图。match_id 为多人房间 ID。"""
        try:
            drawn = await draw_rating(match_id.strip(), return_data=True)
            image, rating_data = drawn
            await _send_image(ctx, image)
            text = json.dumps(
                {
                    "status": "sent",
                    "message": f"已发送 match {match_id} rating 图，并返回结构化评分数据。",
                    "rating": _match_rating_to_summary(rating_data),
                },
                ensure_ascii=False,
            )
            return _image_tool_result(text, image, include_image_for_analysis)
        except Exception as e:
            return f"发送 match rating 失败: {e}"

    @tool("send_osu_preview")
    async def send_osu_preview(
        map_id: str,
        mode: str | None = "0",
        mods: str = "",
        full: bool = False,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送 beatmap 预览图。mode: 0=std, 1=taiko, 2=ctb/fruits, 3=mania。"""
        try:
            mode = _normalize_mode(mode, "osu") or "0"
            media, extra_text = await _draw_preview(map_id, mode, mods, full)
            if isinstance(media, Path):
                message = UniMessage.video(raw=media.read_bytes(), name=media.name)
            else:
                message = UniMessage.image(raw=media)
            if extra_text:
                message += UniMessage.text("\n" + extra_text)
            await message.send(target=ctx.send_target)
            text = f"已发送谱面 {map_id} 的 {NGM[mode]} {'完整预览视频' if isinstance(media, Path) else '预览图'}。"
            if extra_text:
                text += "\n" + extra_text
            if isinstance(media, Path):
                return text
            return _image_tool_result(text, media, include_image_for_analysis)
        except NetworkError as e:
            return f"查询谱面预览失败: {e}"
        except Exception as e:
            return f"发送谱面预览失败: {e}"

    @tool("send_osu_background")
    async def send_osu_background(map_id: str, include_image_for_analysis: bool = False) -> str | list[ContentBlock]:
        """提取并发送 beatmap 背景图。map_id 为谱面 ID。"""
        try:
            image = await get_bg(map_id.strip())
            raw = BytesIO()
            image.convert("RGB").save(raw, "jpeg")
            await _send_image(ctx, raw)
            return _image_tool_result(f"已发送谱面 {map_id} 的背景图。", raw, include_image_for_analysis)
        except NetworkError as e:
            return f"获取谱面背景失败: {e}"
        except Exception as e:
            return f"发送谱面背景失败: {e}"

    @tool("send_osu_medal")
    async def send_osu_medal(name: str) -> str:
        """查询并发送 osu medal/成就获得方式。name 为 medal 名称。"""
        try:
            response = await safe_async_get(f"https://osekai.net/medals/api/public/get_medal.php?medal={name}")
            medal_data = response.json()
            if "MedalID" not in medal_data:
                return "没有找到这个 medal，可能是名字写错了"

            words = ""
            if medal_data["Restriction"] != "NULL":
                words += f"限制模式：{medal_data['Restriction']}\n"
            words += "获得方式：\n"
            if medal_data["Name"] in medal_json:
                words += medal_json[medal_data["Name"]]["MedalSolution"]
            else:
                words += medal_data["Solution"] or medal_data["Instructions"]
                words = _strip_medal_html(words)
            if medal_data["PackID"]:
                words += f"\nhttps://osu.ppy.sh/beatmaps/packs/{medal_data['PackID'].rstrip(',,,')}"

            await (UniMessage.image(url=medal_data["Link"]) + words).send(target=ctx.send_target)
            beatmaps = medal_data.get("beatmaps") or []
            if beatmaps:
                msg = UniMessage()
                for beatmap in beatmaps[:5]:
                    msg += (
                        f"{beatmap['SongTitle']} [{beatmap['DifficultyName']}]\n"
                        f"{beatmap['Difficulty']}⭐\nhttps://osu.ppy.sh/b/{beatmap['BeatmapID']}\n"
                    )
                await msg.send(target=ctx.send_target)
            return f"已发送 medal {medal_data['Name']} 的获得方式。\n{words}"
        except Exception as e:
            return f"查询 medal 失败: {e}"

    @tool("send_osu_map_info")
    async def send_osu_map_info(map_id: str, mods: str = "", mode: str | None = None) -> str:
        """
        查询并发送 osu beatmap 信息图。map_id 是单张谱面 ID；mods 可填 HDHR、DT 等；
        mode 可指定 std 谱面的转谱模式：0=std、1=taiko、2=ctb、3=mania。
        """
        try:
            target_mode = _normalize_mode(mode, "osu") if mode is not None else None
            data = await draw_map_info(
                int(map_id),
                mods2list(mods) if mods else [],
                int(target_mode) if target_mode is not None else None,
            )
            await _send_image(ctx, data)
            return f"已发送谱面 {map_id} 信息图"
        except NetworkError as e:
            return f"查询谱面失败: {e}"
        except Exception as e:
            return f"发送谱面信息失败: {e}"

    @tool("send_osu_beatmapset_info")
    async def send_osu_beatmapset_info(set_id: str) -> str:
        """
        查询并发送 osu beatmapset 信息图。set_id 是谱面集 ID。
        """
        try:
            data = await draw_bmap_info(set_id)
            await _send_image(ctx, data)
            return f"已发送 beatmapset {set_id} 信息图"
        except NetworkError as e:
            return f"查询 beatmapset 失败: {e}"
        except Exception as e:
            return f"发送 beatmapset 信息失败: {e}"

    return AgentToolBundle(
        tools=[
            get_osubot_command_help,
            send_osu_user_info,
            send_osu_bp,
            get_osu_bp_data,
            get_osu_bp_range,
            send_osu_bp_list,
            send_osu_firsts,
            send_osu_recent_or_pr,
            send_osu_score,
            search_osu_beatmaps,
            get_osu_scores_by_map_name,
            send_osu_history,
            send_osu_bp_analysis,
            send_osu_recommend,
            send_osu_profile_url,
            send_osu_match_history,
            send_osu_match_rating,
            send_osu_preview,
            send_osu_background,
            send_osu_medal,
            send_osu_map_info,
            send_osu_beatmapset_info,
        ],
        instructions=[
            "- 用户询问“怎么用/什么指令/有哪些命令/格式或简称”时，调用 get_osubot_command_help，"
            "根据问题选择 topic，并原样保留工具返回的斜杠指令和示例。",
            "- 区分教学和执行：例如“BP 指令怎么用”只查 command help；“帮我查 BP”才调用成绩工具。"
            "不要为了演示用法而调用会发图或执行查询的工具。",
            "- 当前请求的发言用户 ID 已由系统在工具上下文中绑定，不会展示给你，也不需要你知道。",
            "- 未指定玩家、用户说“我/自己/我的”时，禁止追问或猜测个人 ID；不要传 username 或 target_user_id，"
            "直接调用工具，工具会使用当前发言用户绑定的 osu 账号。",
            "- 用户想查被 @ 的群友时，不要传 username；工具会自动读取消息中的非 bot @ 目标并使用该群友绑定账号。",
            "- 用户明确给出群友 QQ/user_id 时，传 target_user_id；这会查询该群友绑定的 osu 账号。",
            "- 未指定模式时，不要传 mode；工具会使用绑定账号的默认模式。官网成绩默认查询 lazer + stable。",
            "- send_osu_bp 会直接发送一张结果图。只要求查询/看图时 purpose=view，成功后调用 finish，"
            "不要再发送同义文字。",
            "- send_osu_firsts 会直接发送玩家的第一名成绩列表图；成功后调用 finish，不要再发送同义文字。",
            "- 用户问单个 BP“打得怎么样/发挥如何/分析/评价/看看问题”时，调用 send_osu_bp 并传 purpose=analyze；"
            "根据工具返回的结构化成绩给出简短评价，不要重复发图。",
            "- 比较多个 BP、分析多个指定 BP 的差异时，调用 get_osu_bp_data；它只返回结构化数据且不会发图。"
            "不要用它处理普通的单个 BP 看图请求。每次最多传 10 个 BP 序号，超过会因结果过长被截断丢失中间数据；"
            "需要更多时分成多次调用。",
            "- 用户要求评价/分析一段 BP 范围或整体 BP（如“评价一下我的 bp1-200”）时，按两段式执行："
            "① 先调用 send_osu_bp_list 发送 BP 列表图，range_text 填用户给的范围（未给则 1-200）；"
            "② 再调用 get_osu_bp_range 分段读取结构化数据，从 1-20 开始，has_more=true 时按 next_start 续读；"
            "评价整体/全量 BP 时可一直读到 has_more=false，覆盖越全评价越准确，不要只读前一两段就下结论；"
            "③ 最后基于读到的数据给出评价，不要依赖图片内容。",
            "- get_osu_bp_range: 按范围分页读取 BP 数据（每次最多 20 条、不发图），"
            "用于分析整体 BP 构成/实力/吃分分布。范围宽度必须 ≤20，不要传 1-200 这样的宽范围。"
            "它与 send_osu_bp_list 不同：后者用于发图展示。",
            "- 分析/评价类请求（锐评发挥、评价实力、分析成绩细节）直接用工具返回的 JSON 结构化数据"
            "（info/scores 字段），不要依赖图片内容，也不要传 include_image_for_analysis。"
            "图片只是发给用户的展示物，不是你的分析数据源。",
            "- include_image_for_analysis 仅在用户明确要求看渲染图本身（如排版、背景、预览效果）时才传 true；"
            "普通分析请求一律省略它，使用工具返回的结构化数据即可。",
            "- send_osu_user_info: 用户想查 osu 玩家资料、info、个人信息图时使用。"
            "工具会返回结构化资料（pp/rank/acc/游玩次数等），可直接用于评价玩家实力，无需看图。",
            "- send_osu_bp: 用户想查某个 bp 序号、最好成绩、bp1/bp10 时使用。",
            "- get_osu_bp_data: 仅用于读取多个指定 BP 的数据以进行比较或复杂分析，不发送图片。",
            "- send_osu_bp_list: 用户想实际查询 bp 列表、bl/bplist/pfm、一段 bp 范围或筛选 BP 时使用。"
            "无筛选默认 1-30；有 filters 且用户没指定范围时省略 range_text，让工具自动搜索 1-200。"
            "筛选后只有一条时工具会自动发送单张成绩图并返回结构化成绩，多条时才发送列表图。",
            "- send_osu_firsts: 用户想查 firsts、榜一、第一名成绩、全球排行榜第一记录时使用；"
            "它只查询 osu! 官网。不要把 BP1/最好成绩误当成榜一，BP1 应使用 send_osu_bp。"
            "无筛选默认 1-30；有 filters 且用户没指定范围时省略 range_text，让工具自动搜索 1-200。",
            "- BP/榜一筛选要写入 send_osu_bp_list.filters 或 send_osu_firsts.filters，"
            "不要把筛选文本放进 username，也不要传完整的 `/bl`、`/first` 指令。"
            "多个条件以空格连接且为 AND：pp/acc/stars/miss/combo/bpm/length/mapper/title/version/rank/client/date/"
            "days/hours/speed/mods；简写 p/a/s/m/c/b/len/mp/t/v/r/cl/sp/mod。",
            "- 将自然语言 BP/榜一条件转换为对应工具的 filters：‘300pp以上’=`300pp+`，‘98acc以上’=`98a+`，"
            "‘5到7星’=`5-7*`，‘最近7天’=`7d`，‘最近一天/最近24小时’=`24h`，‘FC/零失误’=`fc`，"
            "‘非FC’=`nofc`，‘不要DT’=`-DT`，‘仅HDHR’=`=HDHR`。",
            "- Mods 参数语义：mods='HDHR' 表示成绩至少包含 HD 和 HR；精确 Mods 或排除 Mods 应写 filters："
            "mods=HDHR / =HDHR、mods!=DT / -DT。标题、谱师等文本搜索使用 t~关键词、mp~谱师；含空格时加引号。",
            "- send_osu_recent_or_pr: 用户想实际查询 recent/re 或 pr/最近通过的单条成绩时使用。"
            "工具会返回该成绩的结构化数据，可据此评价发挥，无需依赖图片。",
            "- search_osu_beatmaps: 用户只给出歌名、别名、艺术家、谱师或难度名而没有 beatmap ID/链接时，"
            "先用它搜索。候选唯一或用户描述能唯一匹配时，再把 beatmap_id 交给成绩、谱面信息、预览或背景工具；"
            "多个候选无法确定时列出简短候选让用户选择，禁止擅自使用第一项或编造 ID。",
            "- get_osu_scores_by_map_name: 用户以‘xxx 图打了多少/在 xxx 的成绩’这类名称描述谱面且没给 ID 时，"
            "直接调用它。只查询时 purpose=view，工具发送图片后立即结束，不要自行输出 Markdown 列表，也不要补充或复述；"
            "要求评价、分析发挥时 purpose=analyze，根据返回的 scores 给出分析，不要重复发图。"
            "未指定模式时必须省略 mode，让工具优先使用绑定默认模式或该玩家的"
            "osu! 默认游玩模式；不要先调用不含玩家上下文的 search_osu_beatmaps。",
            "- send_osu_score: 用户给出 beatmap ID/链接，或明确要求某个已确定难度的成绩图时使用。"
            "工具会返回该成绩的结构化数据，可据此分析发挥。"
            "仅要求按名称查看成绩列表时不要调用它逐张发图。",
            "- send_osu_history: 用户想查 pp/rank 历史、history、最近一段时间变化曲线时使用。"
            "工具会返回结构化历史数据（起止/峰值 pp、rank 变化、最近数据点），可直接用于分析趋势。",
            "- send_osu_bp_analysis: 用户想查 bp 分析、bpa、bp 构成、mod/mapper/长度贡献时使用。"
            "工具会返回结构化分析数据（加权/总 pp、平均 acc/星数/bpm、rank 分布、mod/mapper 贡献）。",
            "- send_osu_recommend: 用户想要推荐谱面、推荐铺面、recommend 时使用；"
            "工具会返回结构化推荐数据（标题/stars/预测 pp 与 acc/mods），可直接向用户描述推荐理由。"
            "普通推荐/综合/好玩且能打传 target='mixed'，想吃分/上分传 target='farm'，"
            "想难一点/更难/冲分/高难传 target='peak'，想练习/风格推荐传 target='style'，"
            "想均衡传 target='balanced'。",
            "- send_osu_profile_url: 用户想要 osu 主页链接、个人主页、mu 时使用。",
            "- send_osu_match_history: 用户想查 match/multiplayer 对局历史图时使用。"
            "工具会返回结构化对局数据（双方队伍、胜场、每局比分与 MVP），可直接用于分析对局。",
            "- send_osu_match_rating: 用户想查 match rating、多人房评分图时使用。"
            "工具会返回结构化评分数据（各玩家 rating/胜率/总分/MVP），可直接用于评价表现。",
            "- send_osu_preview: 用户想看谱面预览、preview、完整预览时使用。",
            "- send_osu_background: 用户想提取谱面背景、bg/getbg、背景图时使用。",
            "- send_osu_medal: 用户想查 medal/成就获得方式时使用。",
            "- send_osu_map_info: 用户想实际查询单张谱面 m/map/beatmap 信息时使用。",
            "- send_osu_beatmapset_info: 用户想实际查询谱面集 bm/bmap/beatmapset 信息时使用。",
        ],
    )
