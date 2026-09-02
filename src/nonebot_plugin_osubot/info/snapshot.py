from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..database.models import InfoData, UserData
from ..schema.user import UnifiedUser, User, UserStatistics


_SNAPSHOT_VALUE_FIELDS = (
    "c_rank",
    "g_rank",
    "pp",
    "acc",
    "pc",
    "count",
    "ranked_score",
    "total_score",
    "max_combo",
    "count_xh",
    "count_x",
    "count_sh",
    "count_s",
    "count_a",
    "replays",
    "play_time",
    "badge_count",
)


class InfoSnapshotStore(Protocol):
    async def save(self, users: Sequence[User]) -> int: ...

    async def save_mode(self, user: UnifiedUser, osu_mode: int) -> int: ...


def _make_info_data(
    osu_id: int,
    stats: UserStatistics | None,
    osu_mode: int,
    snapshot_date: date,
    badge_count: int = 0,
) -> InfoData:
    if stats is None:
        return InfoData(
            osu_id=osu_id,
            c_rank=0,
            g_rank=0,
            pp=0,
            acc=0,
            pc=0,
            count=0,
            osu_mode=osu_mode,
            date=snapshot_date,
        )

    gc = stats.grade_counts
    return InfoData(
        osu_id=osu_id,
        c_rank=stats.country_rank,
        g_rank=stats.global_rank,
        pp=stats.pp,
        acc=stats.hit_accuracy,
        pc=stats.play_count,
        count=stats.total_hits,
        osu_mode=osu_mode,
        date=snapshot_date,
        ranked_score=stats.ranked_score,
        total_score=stats.total_score,
        max_combo=stats.maximum_combo,
        count_xh=gc.ssh,
        count_x=gc.ss,
        count_sh=gc.sh,
        count_s=gc.s,
        count_a=gc.a,
        replays=stats.replays_watched_by_others,
        play_time=stats.play_time,
        badge_count=badge_count,
    )


class SqlInfoSnapshotStore:
    """Insert or refresh daily snapshots in one transaction."""

    def __init__(self) -> None:
        self._save_lock = asyncio.Lock()

    @staticmethod
    def _update_row(target: InfoData, source: InfoData) -> None:
        for field in _SNAPSHOT_VALUE_FIELDS:
            setattr(target, field, getattr(source, field))

    async def _save_rows(self, rows: Sequence[InfoData], usernames: dict[int, str]) -> int:
        if not rows:
            return 0

        snapshot_date = date.today()
        user_ids = list({row.osu_id for row in rows})
        modes = list({row.osu_mode for row in rows})
        async with self._save_lock, get_session() as session:
            existing_rows = (
                await session.scalars(
                    select(InfoData).where(
                        InfoData.osu_id.in_(user_ids),
                        InfoData.osu_mode.in_(modes),
                        InfoData.date == snapshot_date,
                    )
                )
            ).all()
            existing_by_pair: dict[tuple[int, int], list[InfoData]] = {}
            for existing in existing_rows:
                existing_by_pair.setdefault((existing.osu_id, existing.osu_mode), []).append(existing)

            for row in rows:
                matching_rows = existing_by_pair.get((row.osu_id, row.osu_mode))
                if matching_rows:
                    for existing in matching_rows:
                        self._update_row(existing, row)
                else:
                    session.add(row)
                    existing_by_pair[(row.osu_id, row.osu_mode)] = [row]

            bound_users = (await session.scalars(select(UserData).where(UserData.osu_id.in_(user_ids)))).all()
            for bound_user in bound_users:
                username = usernames.get(bound_user.osu_id)
                if username is not None and bound_user.osu_name != username:
                    bound_user.osu_name = username

            await session.commit()
        return len(user_ids)

    async def save(self, users: Sequence[User]) -> int:
        available_users = [user for user in users if user.statistics_rulesets]
        if not available_users:
            return 0

        snapshot_date = date.today()
        rows: list[InfoData] = []
        for user in available_users:
            rulesets = user.statistics_rulesets
            if rulesets is None:
                continue
            badge_count = len(user.badges) if user.badges else 0
            mode_stats = (
                (rulesets.osu, 0),
                (rulesets.taiko, 1),
                (rulesets.fruits, 2),
                (rulesets.mania, 3),
            )
            rows.extend(
                _make_info_data(user.id, stats, mode, snapshot_date, badge_count) for stats, mode in mode_stats
            )
        return await self._save_rows(rows, {user.id: user.username for user in available_users})

    async def save_mode(self, user: UnifiedUser, osu_mode: int) -> int:
        if user.statistics is None:
            return 0
        if osu_mode not in range(4):
            raise ValueError(f"不支持保存模式 {osu_mode} 的官方快照")
        row = _make_info_data(
            user.id,
            user.statistics,
            osu_mode,
            date.today(),
            len(user.badges) if user.badges else 0,
        )
        return await self._save_rows([row], {user.id: user.username})


info_snapshot_store: InfoSnapshotStore = SqlInfoSnapshotStore()
