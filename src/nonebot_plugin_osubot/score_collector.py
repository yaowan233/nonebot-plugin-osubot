from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import date

from nonebot.log import logger
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from .api import get_user_scores
from .database.models import InfoData, UserData
from .schema.score import UnifiedScore
from .network.scheduler import RequestPriority, osu_api_priority
from .score_history import ScoreHistoryStore, score_history_store
from .utils import NGM


ScoreFetcher = Callable[..., Awaitable[list[UnifiedScore]]]
CollectionTarget = tuple[int, str]


@dataclass(frozen=True)
class CollectorReport:
    targets: int
    saved: int
    failed: int


def active_score_targets(rows: Iterable[tuple[int, int, int, date]]) -> set[CollectionTarget]:
    """Find user/ruleset pairs whose play count increased between two snapshots."""
    snapshots: dict[tuple[int, int], list[tuple[date, int]]] = {}
    for user_id, ruleset_id, play_count, snapshot_date in rows:
        snapshots.setdefault((user_id, ruleset_id), []).append((snapshot_date, play_count))

    targets: set[CollectionTarget] = set()
    for (user_id, ruleset_id), values in snapshots.items():
        if str(ruleset_id) not in NGM:
            continue
        values.sort(key=lambda item: item[0], reverse=True)
        if len(values) >= 2 and values[0][1] > values[1][1]:
            targets.add((user_id, NGM[str(ruleset_id)]))
    return targets


async def find_active_bound_users() -> set[CollectionTarget]:
    """Return only bound users who played in a ruleset since the previous snapshot."""
    async with get_session() as session:
        dates = list(
            await session.scalars(
                select(InfoData.date).distinct().order_by(InfoData.date.desc()).limit(2)
            )
        )
        if len(dates) < 2:
            return set()

        rows = (
            await session.execute(
                select(InfoData.osu_id, InfoData.osu_mode, InfoData.pc, InfoData.date).where(
                    InfoData.date.in_(dates),
                    InfoData.osu_id.in_(select(UserData.osu_id)),
                )
            )
        ).all()
    return active_score_targets(rows)


class ScoreCollector:
    """Bounded worker pool that archives only scores accepted by the history store."""

    def __init__(
        self,
        history: ScoreHistoryStore,
        *,
        fetcher: ScoreFetcher = get_user_scores,
        concurrency: int = 2,
        recent_limit: int = 200,
    ):
        self._history = history
        self._fetcher = fetcher
        self._concurrency = max(1, concurrency)
        self._recent_limit = max(1, recent_limit)

    async def collect(self, targets: Iterable[CollectionTarget]) -> CollectorReport:
        unique_targets = set(targets)
        if not unique_targets:
            return CollectorReport(targets=0, saved=0, failed=0)

        queue: asyncio.Queue[CollectionTarget | None] = asyncio.Queue(maxsize=self._concurrency * 2)
        saved = 0
        failed = 0

        async def worker() -> None:
            nonlocal saved, failed
            while True:
                target = await queue.get()
                try:
                    if target is None:
                        return
                    user_id, mode = target
                    with osu_api_priority(RequestPriority.BACKGROUND):
                        scores = await self._fetcher(
                            user_id,
                            mode,
                            "recent",
                            source="osu",
                            legacy_only=False,
                            include_failed=True,
                            limit=self._recent_limit,
                        )
                    saved += await self._history.save(scores)
                except Exception:
                    failed += 1
                    logger.exception(f"采集玩家 {target} 的成绩历史失败")
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(self._concurrency)]
        for target in unique_targets:
            await queue.put(target)
        for _ in workers:
            await queue.put(None)
        await queue.join()
        await asyncio.gather(*workers)
        return CollectorReport(targets=len(unique_targets), saved=saved, failed=failed)


async def collect_active_score_history(*, concurrency: int = 2, recent_limit: int = 200) -> CollectorReport:
    targets = await find_active_bound_users()
    collector = ScoreCollector(
        score_history_store,
        concurrency=concurrency,
        recent_limit=recent_limit,
    )
    report = await collector.collect(targets)
    logger.info(
        f"成绩历史采集完成：活跃模式 {report.targets} 个，新增 {report.saved} 条，失败 {report.failed} 个"
    )
    return report
