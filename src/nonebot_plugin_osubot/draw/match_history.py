import re
from pathlib import Path
from datetime import datetime
from statistics import mode

from nonebot_plugin_htmlrender import template_to_pic

from ..api import api_info
from ..schema.match import Match


TEMPLATE_PATH = Path(__file__).parent / "match_templates"
MOD_PATH = Path(__file__).parent.parent / "osufile" / "mods"


def _score_mods(game_mods: list[str], player_mods: list[str]) -> list[str]:
    mods = list(dict.fromkeys([*game_mods, *player_mods]))
    if "NC" in mods and "DT" in mods:
        mods.remove("DT")
    return [mod for mod in mods if mod not in {"CL", "NM", "FM"} and (MOD_PATH / f"{mod}.png").exists()]


def _match_names(name: str) -> tuple[str, str, str]:
    matched = re.search(r"([^:]+): [\(（](.+?)[\)）] vs [\(（](.+?)[\)）]", name, re.IGNORECASE)
    if not matched:
        return name, "红队", "蓝队"
    return matched.group(1), matched.group(2), matched.group(3)


def _format_time_range(match: dict) -> tuple[str, str]:
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


def prepare_match_data(match_info: Match, match_id: str) -> dict:
    games = [
        event.game
        for event in match_info.events
        if event.detail.type == "other" and event.game is not None and event.game.scores
    ]
    if not games:
        raise ValueError("该多人房没有可展示的对局")

    team_type = mode([game.team_type for game in games])
    is_team = team_type == "team-vs"
    users = {user.id: user for user in match_info.users}
    title, red_name, blue_name = _match_names(match_info.match["name"])
    time_range, duration = _format_time_range(match_info.match)
    red_wins = 0
    blue_wins = 0
    rendered_games = []

    for index, game in enumerate(games, start=1):
        beatmap = game.beatmap
        beatmapset = beatmap.beatmapset if beatmap else None
        scores = [score for score in game.scores if score.score > 0]
        if not scores:
            continue

        player_rows = []
        for score in sorted(scores, key=lambda item: item.score, reverse=True):
            user = users.get(score.user_id)
            player_rows.append(
                {
                    "user_id": score.user_id,
                    "name": user.username if user else str(score.user_id),
                    "avatar": user.avatar_url if user else f"https://a.ppy.sh/{score.user_id}",
                    "team": (score.match or {}).get("team", "none"),
                    "score": score.score,
                    "accuracy": score.accuracy * 100,
                    "combo": score.max_combo,
                    "mods": _score_mods(game.mods, score.mods),
                }
            )

        red_score = sum(player["score"] for player in player_rows if player["team"] == "red")
        blue_score = sum(player["score"] for player in player_rows if player["team"] == "blue")
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
                    else f"https://assets.ppy.sh/beatmaps/{beatmap.beatmapset_id}/covers/cover.jpg"
                    if beatmap
                    else ""
                ),
                "stars": beatmap.difficulty_rating if beatmap else 0,
                "winner": winner,
                "red_score": red_score,
                "blue_score": blue_score,
                "players": player_rows,
                "red_players": [player for player in player_rows if player["team"] == "red"],
                "blue_players": [player for player in player_rows if player["team"] == "blue"],
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
            (max(len(game["red_players"]), len(game["blue_players"])) for game in rendered_games),
            default=0,
        ),
        "duration": duration,
        "time_range": time_range,
        "complete": bool(match_info.match.get("end_time")),
        "games": rendered_games,
    }


async def draw_match_card(data: dict) -> bytes:
    return await template_to_pic(str(TEMPLATE_PATH), "index.html", data, type="png")


async def draw_match_history(match_id: str) -> bytes:
    raw = await api_info("matches", f"https://osu.ppy.sh/api/v2/matches/{match_id}")
    return await draw_match_card(prepare_match_data(Match(**raw), match_id))
