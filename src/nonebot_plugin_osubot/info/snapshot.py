from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..database.models import InfoData, UserData
from ..schema.user import User, UserStatistics


class InfoSnapshotStore(Protocol):
    async def save(self, users: Sequence[User]) -> int: ...


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
    """Persist one daily snapshot per user and ruleset in one transaction."""

    async def save(self, users: Sequence[User]) -> int:
        available_users = [user for user in users if user.statistics_rulesets]
        if not available_users:
            return 0

        snapshot_date = date.today()
        user_ids = [user.id for user in available_users]
        usernames = {user.id: user.username for user in users}

        async with get_session() as session:
            existing_pairs = set(
                (
                    await session.execute(
                        select(InfoData.osu_id, InfoData.osu_mode).where(
                            InfoData.osu_id.in_(user_ids),
                            InfoData.date == snapshot_date,
                        )
                    )
                ).all()
            )

            rows: list[InfoData] = []
            updated_users: set[int] = set()
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
                for stats, mode in mode_stats:
                    if (user.id, mode) in existing_pairs:
                        continue
                    rows.append(_make_info_data(user.id, stats, mode, snapshot_date, badge_count))
                    updated_users.add(user.id)

            if rows:
                session.add_all(rows)

            bound_users = (await session.scalars(select(UserData).where(UserData.osu_id.in_(list(usernames))))).all()
            for bound_user in bound_users:
                username = usernames.get(bound_user.osu_id)
                if username is not None and bound_user.osu_name != username:
                    bound_user.osu_name = username

            await session.commit()
        return len(updated_users)


info_snapshot_store: InfoSnapshotStore = SqlInfoSnapshotStore()
