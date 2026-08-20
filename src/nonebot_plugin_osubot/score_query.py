from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from expiringdict import ExpiringDict

from .api import get_user_scores, osu_api
from .utils import FGM
from .schema import NewScore
from .schema.score import NewStatistics, UnifiedBeatmap, UnifiedScore, get_score_version
from .score_history import ScoreHistoryStore, has_leaderboard, score_history_store


@dataclass(frozen=True)
class ScoreLookup:
    scores: list[UnifiedScore]
    source: Literal["official", "history"]
    complete: bool
    position: int | str | None = None


def map_score_to_unified(score: NewScore, map_json: dict) -> UnifiedScore:
    beatmap = score.beatmap
    beatmapset = score.beatmapset or (beatmap.beatmapset if beatmap else None)
    beatmapset_json = map_json.get("beatmapset") or {}
    return UnifiedScore(
        score_id=getattr(score, "id", None),
        user_id=getattr(score, "user_id", None),
        mods=score.mods,
        ruleset_id=score.ruleset_id,
        rank=score.rank,
        accuracy=score.accuracy * 100,
        total_score=score.total_score,
        ended_at=datetime.strptime(score.ended_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8),
        max_combo=score.max_combo,
        statistics=score.statistics or NewStatistics(),
        legacy_total_score=score.legacy_total_score,
        passed=score.passed,
        pp=score.pp,
        score_version=get_score_version(score.legacy_score_id),
        beatmap=UnifiedBeatmap(
            id=score.beatmap_id,
            set_id=(beatmapset.id if beatmapset else map_json["beatmapset_id"]),
            artist=beatmapset.artist if beatmapset else str(beatmapset_json.get("artist") or ""),
            title=beatmapset.title if beatmapset else str(beatmapset_json.get("title") or ""),
            version=beatmap.version if beatmap else str(map_json.get("version") or ""),
            creator=beatmapset.creator if beatmapset else str(beatmapset_json.get("creator") or ""),
            total_length=int(beatmap.total_length if beatmap else map_json.get("total_length") or 0),
            mode=beatmap.mode_int if beatmap else int(map_json.get("mode_int") or 0),
            bpm=float((beatmap.bpm if beatmap else None) or map_json.get("bpm") or 0),
            cs=float(beatmap.cs if beatmap else map_json.get("cs") or 0),
            od=float(beatmap.accuracy if beatmap else map_json.get("accuracy") or 0),
            ar=float(beatmap.ar if beatmap else map_json.get("ar") or 0),
            hp=float(beatmap.drain if beatmap else map_json.get("drain") or 0),
            stars=float(beatmap.difficulty_rating if beatmap else map_json.get("difficulty_rating") or 0),
            checksum=beatmap.checksum if beatmap else map_json.get("checksum"),
            user_id=beatmap.user_id if beatmap else map_json.get("user_id"),
            convert=beatmap.convert if beatmap else bool(map_json.get("convert", False)),
            status=beatmap.status if beatmap else map_json.get("status"),
            is_scoreable=beatmap.is_scoreable if beatmap else map_json.get("is_scoreable"),
        ),
        beatmapset=beatmapset,
    )


class ScoreQuery:
    """Choose the authoritative score source behind one small query interface."""

    def __init__(
        self,
        history: ScoreHistoryStore,
        recent_fetcher: Callable[..., Awaitable[list[UnifiedScore]]] = get_user_scores,
    ):
        self._history = history
        self._recent_fetcher = recent_fetcher
        self._recent_misses: ExpiringDict = ExpiringDict(max_len=10_000, max_age_seconds=600)

    @staticmethod
    def _has_leaderboard(map_json: dict) -> bool:
        return has_leaderboard(map_json.get("status"), map_json.get("is_scoreable"))

    async def _history_scores(
        self,
        user_id: int,
        mode: str,
        map_json: dict,
        *,
        legacy_only: bool,
    ) -> list[UnifiedScore]:
        beatmap_id = int(map_json["id"])
        ruleset_id = FGM[mode]
        scores = await self._history.find(user_id, beatmap_id, ruleset_id)
        matching = [score for score in scores if not legacy_only or score.score_version == "stable"]
        if matching:
            return matching

        miss_key = (user_id, beatmap_id, ruleset_id, legacy_only)
        if self._recent_misses.get(miss_key):
            return []

        # First query after deployment gets one bounded chance to seed the local
        # archive from osu!'s recent endpoint instead of waiting for the nightly job.
        recent = await self._recent_fetcher(
            user_id,
            mode,
            "recent",
            source="osu",
            legacy_only=legacy_only,
            include_failed=True,
            limit=200,
        )
        await self._history.save(recent)
        matching = [
            score
            for score in recent
            if score.beatmap is not None
            and score.beatmap.id == beatmap_id
            and (not legacy_only or score.score_version == "stable")
        ]
        if not matching:
            self._recent_misses[miss_key] = True
        return matching

    async def list_beatmap_scores(
        self,
        user_id: int,
        mode: str,
        map_json: dict,
        *,
        legacy_only: bool,
    ) -> ScoreLookup:
        if not self._has_leaderboard(map_json):
            scores = await self._history_scores(
                user_id,
                mode,
                map_json,
                legacy_only=legacy_only,
            )
            return ScoreLookup(scores=scores, source="history", complete=False)

        response = await osu_api(
            "score",
            user_id,
            mode,
            int(map_json["id"]),
            legacy_only=int(legacy_only),
        )
        scores = [map_score_to_unified(NewScore(**item), map_json) for item in response.get("scores", [])]
        return ScoreLookup(scores=scores, source="official", complete=True)

    async def best_beatmap_score(
        self,
        user_id: int,
        mode: str,
        map_json: dict,
        *,
        legacy_only: bool,
    ) -> ScoreLookup:
        if not self._has_leaderboard(map_json):
            scores = await self._history_scores(
                user_id,
                mode,
                map_json,
                legacy_only=legacy_only,
            )
            best = max(scores, key=lambda score: score.total_score, default=None)
            return ScoreLookup(scores=[best] if best else [], source="history", complete=False)

        response = await osu_api(
            "best_score",
            user_id,
            mode,
            int(map_json["id"]),
            legacy_only=int(legacy_only),
        )
        score = map_score_to_unified(NewScore(**response["score"]), map_json)
        return ScoreLookup(
            scores=[score],
            source="official",
            complete=True,
            position=response.get("position"),
        )


score_query = ScoreQuery(score_history_store)
