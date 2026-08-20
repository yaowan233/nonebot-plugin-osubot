import asyncio
from datetime import date, datetime

import pytest
from sqlalchemy import delete, select


def _score(score_id: int, *, status: str = "graveyard"):
    from nonebot_plugin_osubot.schema.score import NewStatistics, UnifiedBeatmap, UnifiedScore

    return UnifiedScore(
        score_id=score_id,
        user_id=28_231_505,
        mods=[],
        ruleset_id=3,
        rank="A",
        accuracy=92.95,
        total_score=740_031,
        ended_at=datetime(2026, 8, 14, 12, 48, 16),
        max_combo=899,
        statistics=NewStatistics(perfect=4_585, great=2_935, good=826, ok=164, meh=58, miss=121),
        passed=True,
        beatmap=UnifiedBeatmap(
            id=3_476_964,
            set_id=1_704_737,
            artist="Muses",
            title="Malody 4K Regular Dans v3",
            version="Regular-8",
            creator="Rin",
            total_length=584,
            mode=3,
            bpm=160,
            cs=4,
            od=8.5,
            ar=0,
            hp=8,
            stars=5.67,
            status=status,
            is_scoreable=status in {"ranked", "approved", "qualified", "loved"},
        ),
    )


@pytest.mark.asyncio
async def test_history_store_only_saves_no_leaderboard_scores_and_is_idempotent():
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_osubot.database.models import ScoreHistoryData
    from nonebot_plugin_osubot.score_history import SqlScoreHistoryStore

    history_id = 9_100_000_000_000_001
    ranked_id = 9_100_000_000_000_002
    async with get_session() as session:
        await session.execute(
            delete(ScoreHistoryData).where(ScoreHistoryData.score_id.in_([history_id, ranked_id]))
        )
        await session.commit()

    store = SqlScoreHistoryStore()
    assert await store.save([_score(history_id), _score(ranked_id, status="ranked")]) == 1
    assert await store.save([_score(history_id)]) == 0

    found = await store.find(28_231_505, 3_476_964, 3)
    matched = [score for score in found if score.score_id == history_id]
    assert [score.score_id for score in matched] == [history_id]
    assert matched[0].beatmap.status == "graveyard"

    async with get_session() as session:
        stored_ids = set(
            await session.scalars(
                select(ScoreHistoryData.score_id).where(
                    ScoreHistoryData.score_id.in_([history_id, ranked_id])
                )
            )
        )
        await session.execute(
            delete(ScoreHistoryData).where(ScoreHistoryData.score_id.in_([history_id, ranked_id]))
        )
        await session.commit()
    assert stored_ids == {history_id}


@pytest.mark.asyncio
async def test_score_query_uses_history_only_for_maps_without_leaderboards(monkeypatch):
    import nonebot_plugin_osubot.score_query as query_module
    from nonebot_plugin_osubot.score_query import ScoreQuery

    expected = _score(9_100_000_000_000_003)

    class History:
        async def save(self, scores):
            return 0

        async def find(self, user_id, beatmap_id, ruleset_id):
            assert (user_id, beatmap_id, ruleset_id) == (28_231_505, 3_476_964, 3)
            return [expected]

    official = []

    async def fake_osu_api(*args, **kwargs):
        official.append((args, kwargs))
        return {"score": {}}

    monkeypatch.setattr(query_module, "osu_api", fake_osu_api)
    query = ScoreQuery(History())
    result = await query.best_beatmap_score(
        28_231_505,
        "mania",
        {"id": 3_476_964, "status": "graveyard", "is_scoreable": False},
        legacy_only=False,
    )

    assert result.scores == [expected]
    assert result.source == "history"
    assert result.complete is False
    assert official == []


@pytest.mark.asyncio
async def test_empty_history_is_seeded_once_from_recent_scores():
    from nonebot_plugin_osubot.score_query import ScoreQuery

    expected = _score(9_100_000_000_000_004)
    saved = []
    fetch_calls = []

    class History:
        async def save(self, scores):
            saved.extend(scores)
            return len(scores)

        async def find(self, user_id, beatmap_id, ruleset_id):
            return []

    async def fetcher(*args, **kwargs):
        fetch_calls.append((args, kwargs))
        return [expected]

    query = ScoreQuery(History(), recent_fetcher=fetcher)
    result = await query.list_beatmap_scores(
        28_231_505,
        "mania",
        {"id": 3_476_964, "status": "graveyard", "is_scoreable": False},
        legacy_only=False,
    )

    assert result.scores == [expected]
    assert saved == [expected]
    assert fetch_calls[0][1]["limit"] == 200


def test_active_targets_compare_each_ruleset_play_count():
    from nonebot_plugin_osubot.score_collector import active_score_targets

    rows = [
        (1, 0, 12, date(2026, 8, 19)),
        (1, 0, 10, date(2026, 8, 18)),
        (1, 3, 20, date(2026, 8, 19)),
        (1, 3, 20, date(2026, 8, 18)),
        (2, 3, 6, date(2026, 8, 19)),
        (2, 3, 1, date(2026, 8, 18)),
    ]

    assert active_score_targets(rows) == {(1, "osu"), (2, "mania")}


@pytest.mark.asyncio
async def test_collector_limits_concurrency_and_deduplicates_targets():
    from nonebot_plugin_osubot.score_collector import ScoreCollector

    active = 0
    peak = 0

    async def fetcher(user_id, mode, scope, **kwargs):
        nonlocal active, peak
        assert scope == "recent"
        assert kwargs["limit"] == 123
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return []

    class History:
        async def save(self, scores):
            return 1

        async def find(self, user_id, beatmap_id, ruleset_id):
            return []

    targets = [(user_id, "mania") for user_id in range(8)]
    collector = ScoreCollector(History(), fetcher=fetcher, concurrency=3, recent_limit=123)
    report = await collector.collect([*targets, targets[0]])

    assert report.targets == 8
    assert report.saved == 8
    assert report.failed == 0
    assert peak == 3
