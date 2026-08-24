from dataclasses import dataclass, field

from nonebot.log import logger

from .api import api_info
from .schema.match import normalize_mods
from .utils import FGM

_ROOM_TYPE_MAP = {
    "team_versus": "team-vs",
    "head_to_head": "head-to-head",
    "tag_coop": "tag-coop",
    "tag_team_vs": "tag-team-vs",
}


@dataclass
class RoomEventMetadata:
    teams_by_playlist: dict[int, dict[str, str]] = field(default_factory=dict)
    fallback_teams: dict[str, str] = field(default_factory=dict)
    aborted_playlist_ids: set[int] = field(default_factory=set)
    room_types_by_playlist: dict[int, str] = field(default_factory=dict)


def is_room_response(raw: dict) -> bool:
    """Return whether an osu! API response uses the lazer room shape."""
    return "match" not in raw and ("playlist" in raw or "category" in raw)


async def fetch_room_event_metadata(room_id: str) -> RoomEventMetadata:
    """Load team, abort, and mode metadata for every room playlist item."""
    metadata = RoomEventMetadata()
    try:
        events_data = await api_info("matches", f"https://osu.ppy.sh/api/v2/rooms/{room_id}/events")
    except Exception as exc:
        logger.debug(f"[room-events] room {room_id}: request failed, using room defaults ({exc})")
        return metadata

    if not isinstance(events_data, dict):
        return metadata

    events = events_data.get("events") or []
    for event in events:
        if not isinstance(event, dict) or event.get("event_type") != "game_aborted":
            continue
        playlist_id = event.get("playlist_item_id")
        try:
            metadata.aborted_playlist_ids.add(int(playlist_id))
        except (TypeError, ValueError):
            continue

    playlist_items = events_data.get("playlist") or events_data.get("playlist_items") or []
    if not playlist_items:
        playlist_items = [
            event["playlist_item"]
            for event in events
            if isinstance(event, dict) and isinstance(event.get("playlist_item"), dict)
        ]

    for item in playlist_items:
        if not isinstance(item, dict):
            continue
        try:
            playlist_id = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue

        details = item.get("details") or {}
        if room_type := details.get("room_type"):
            metadata.room_types_by_playlist[playlist_id] = str(room_type)

        teams = {
            str(user_id): colour
            for user_id, colour in (details.get("teams") or {}).items()
            if colour in {"red", "blue"}
        }
        if teams:
            metadata.teams_by_playlist[playlist_id] = teams
            metadata.fallback_teams.update(teams)

    return metadata


def _legacy_statistics(statistics: dict | None) -> dict:
    statistics = statistics or {}
    return {
        "count_50": statistics.get("count_50", statistics.get("meh")),
        "count_100": statistics.get("count_100", statistics.get("ok")),
        "count_300": statistics.get("count_300", statistics.get("great")),
        "count_geki": statistics.get("count_geki", statistics.get("perfect")),
        "count_katu": statistics.get("count_katu", statistics.get("good")),
        "count_miss": statistics.get("count_miss", statistics.get("miss")),
    }


def _room_score(score: dict, item: dict, team_map: dict[str, str], mode: str) -> dict:
    team = team_map.get(str(score.get("user_id", "")), "none")
    if team not in {"red", "blue"}:
        team = "none"
    return {
        "user_id": score.get("user_id"),
        "score": score.get("total_score", score.get("score", 0)),
        "accuracy": score.get("accuracy", 0),
        "max_combo": score.get("max_combo", 0),
        "mods": normalize_mods(score.get("mods")),
        "perfect": int(bool(score.get("is_perfect_combo", score.get("perfect", False)))),
        "statistics": _legacy_statistics(score.get("statistics")),
        "passed": bool(score.get("passed", True)),
        "rank": score.get("rank") or "F",
        "created_at": score.get("ended_at") or score.get("created_at") or item.get("played_at") or "",
        "mode": mode,
        "mode_int": FGM.get(mode, 0),
        "match": {"team": team, "passed": bool(score.get("passed", True))},
    }


def _room_beatmap(item: dict) -> dict:
    beatmap = item.get("beatmap") or {}
    beatmapset = beatmap.get("beatmapset") or {}
    covers = beatmapset.get("covers") or {}
    cover = covers.get("cover", "")
    return {
        "id": beatmap.get("id"),
        "mode": beatmap.get("mode", "osu"),
        "status": beatmap.get("status", "ranked"),
        "total_length": beatmap.get("total_length", 0),
        "user_id": beatmap.get("user_id", 0),
        "version": beatmap.get("version", ""),
        "difficulty_rating": beatmap.get("difficulty_rating", 0),
        "beatmapset_id": beatmap.get("beatmapset_id"),
        "beatmapset": {
            "id": beatmapset.get("id", beatmap.get("beatmapset_id", 0)),
            "title": beatmapset.get("title", ""),
            "title_unicode": beatmapset.get("title_unicode", beatmapset.get("title", "")),
            "artist": beatmapset.get("artist", ""),
            "artist_unicode": beatmapset.get("artist_unicode", beatmapset.get("artist", "")),
            "creator": beatmapset.get("creator", ""),
            "user_id": beatmapset.get("user_id", 0),
            "source": beatmapset.get("source", ""),
            "status": beatmapset.get("status", "ranked"),
            "nsfw": beatmapset.get("nsfw", False),
            "video": beatmapset.get("video", False),
            "favourite_count": beatmapset.get("favourite_count", 0),
            "play_count": beatmapset.get("play_count", 0),
            "preview_url": beatmapset.get("preview_url", ""),
            "covers": {
                "cover": cover,
                "card": covers.get("card", cover),
                "list": covers.get("list", cover),
                "slimcover": covers.get("slimcover", cover),
            },
        },
    }


async def convert_room_to_match(raw: dict, room_id: str) -> dict:
    """Convert an osu!lazer room response into the legacy Match schema."""
    metadata = await fetch_room_event_metadata(room_id)
    users: dict[int, dict] = {}
    for user in [raw.get("host"), *(raw.get("recent_participants") or [])]:
        if isinstance(user, dict) and user.get("id"):
            users[user["id"]] = user

    events: list[dict] = []
    fallback_room_type = raw.get("type", "head_to_head")
    for item in raw.get("playlist") or []:
        if not item.get("played_at"):
            continue
        try:
            playlist_id = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if playlist_id in metadata.aborted_playlist_ids:
            continue

        try:
            score_data = await api_info(
                "matches", f"https://osu.ppy.sh/api/v2/rooms/{room_id}/playlist/{playlist_id}/scores"
            )
        except Exception as exc:
            logger.debug(f"[room-scores] room {room_id}, playlist {playlist_id}: request failed ({exc})")
            continue

        scores = score_data.get("scores") if isinstance(score_data, dict) else None
        if not scores:
            continue
        for score in scores:
            user = score.get("user")
            if isinstance(user, dict) and user.get("id"):
                users.setdefault(user["id"], user)

        raw_room_type = metadata.room_types_by_playlist.get(playlist_id, fallback_room_type)
        room_type = _ROOM_TYPE_MAP.get(raw_room_type, raw_room_type)
        teams = (
            metadata.teams_by_playlist.get(playlist_id) or metadata.fallback_teams
            if room_type in {"team-vs", "tag-team-vs"}
            else {}
        )
        beatmap = _room_beatmap(item)
        mode = beatmap["mode"]
        game_scores = [_room_score(score, item, teams, mode) for score in scores]
        events.append(
            {
                "id": playlist_id,
                "detail": {"type": "other"},
                "timestamp": item.get("played_at", ""),
                "game": {
                    "id": playlist_id,
                    "beatmap_id": item.get("beatmap_id"),
                    "team_type": room_type,
                    "mods": normalize_mods(item.get("required_mods")),
                    "beatmap": beatmap,
                    "scores": game_scores,
                },
            }
        )

    return {
        "match": {
            "id": raw.get("id"),
            "name": raw.get("name", ""),
            "start_time": raw.get("starts_at") or raw.get("created_at", ""),
            "end_time": raw.get("ends_at"),
        },
        "events": events,
        "users": list(users.values()),
    }
