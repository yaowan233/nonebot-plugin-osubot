from __future__ import annotations

import json
from typing import Protocol

from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .database.models import ScoreHistoryData
from .schema.score import UnifiedScore


LEADERBOARD_STATUSES = frozenset({"ranked", "approved", "qualified", "loved"})


def has_leaderboard(status: str | None, is_scoreable: bool | None = None) -> bool:
    """Return whether osu! exposes a persistent leaderboard for this beatmap."""
    if status:
        return status.casefold() in LEADERBOARD_STATUSES
    return is_scoreable is not False


class ScoreHistoryStore(Protocol):
    async def save(self, scores: list[UnifiedScore]) -> int: ...

    async def find(self, user_id: int, beatmap_id: int, ruleset_id: int) -> list[UnifiedScore]: ...


def _serialize_score(score: UnifiedScore) -> str:
    exclude = {"beatmapset"}
    if hasattr(score, "model_dump_json"):
        return score.model_dump_json(exclude=exclude)
    return score.json(exclude=exclude)


class SqlScoreHistoryStore:
    """SQL adapter for the selective score-history seam.

    Only scores from beatmaps without official leaderboards are accepted. The
    score id is the idempotency key, so repeated daily collection is harmless.
    """

    async def save(self, scores: list[UnifiedScore]) -> int:
        eligible = {
            score.score_id: score
            for score in scores
            if score.score_id is not None
            and score.user_id is not None
            and score.beatmap is not None
            and not has_leaderboard(score.beatmap.status, score.beatmap.is_scoreable)
        }
        if not eligible:
            return 0

        def make_row(score_id: int, score: UnifiedScore) -> ScoreHistoryData:
            return ScoreHistoryData(
                score_id=score_id,
                user_id=score.user_id,
                beatmap_id=score.beatmap.id,
                ruleset_id=score.ruleset_id,
                ended_at=score.ended_at,
                payload=_serialize_score(score),
            )

        async with get_session() as session:
            existing = set(
                await session.scalars(
                    select(ScoreHistoryData.score_id).where(
                        ScoreHistoryData.score_id.in_(list(eligible))
                    )
                )
            )
            missing = [(score_id, score) for score_id, score in eligible.items() if score_id not in existing]
            if not missing:
                return 0

            session.add_all([make_row(score_id, score) for score_id, score in missing])
            try:
                await session.commit()
                return len(missing)
            except IntegrityError:
                # A query worker may race the scheduled collector. Fall back to
                # individual savepoints only on that uncommon path.
                await session.rollback()

            saved = 0
            for score_id, score in missing:
                try:
                    async with session.begin_nested():
                        session.add(make_row(score_id, score))
                        await session.flush()
                    saved += 1
                except IntegrityError:
                    pass
            await session.commit()
        return saved

    async def find(self, user_id: int, beatmap_id: int, ruleset_id: int) -> list[UnifiedScore]:
        async with get_session() as session:
            rows = (
                await session.scalars(
                    select(ScoreHistoryData)
                    .where(
                        ScoreHistoryData.user_id == user_id,
                        ScoreHistoryData.beatmap_id == beatmap_id,
                        ScoreHistoryData.ruleset_id == ruleset_id,
                    )
                    .order_by(ScoreHistoryData.ended_at.desc())
                )
            ).all()
        return [UnifiedScore(**json.loads(row.payload)) for row in rows]


score_history_store: ScoreHistoryStore = SqlScoreHistoryStore()
