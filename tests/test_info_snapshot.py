from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select


def _statistics(pp: float = 1234.5):
    return SimpleNamespace(
        country_rank=12,
        global_rank=345,
        pp=pp,
        hit_accuracy=98.76,
        play_count=100,
        total_hits=2000,
        ranked_score=3000,
        total_score=4000,
        maximum_combo=500,
        replays_watched_by_others=6,
        play_time=700,
        grade_counts=SimpleNamespace(ssh=1, ss=2, sh=3, s=4, a=5),
    )


@pytest.mark.asyncio
async def test_user_info_query_refreshes_official_mode_snapshot(after_nonebot_init, monkeypatch):
    from nonebot_plugin_osubot import api
    from nonebot_plugin_osubot.info.snapshot import info_snapshot_store
    from nonebot_plugin_osubot.server import PlayMode, ServerFeature

    mode = PlayMode.parse("mania")
    user = SimpleNamespace(id=42)
    server = SimpleNamespace(
        parse_mode=lambda value: mode,
        supports=lambda feature, parsed_mode: feature is ServerFeature.OFFICIAL_SNAPSHOTS and parsed_mode == mode,
        get_user=AsyncMock(return_value=user),
    )
    monkeypatch.setattr(api, "get_server", lambda source: server)

    with patch.object(info_snapshot_store, "save_mode", new=AsyncMock(return_value=1)) as save_mode:
        assert await api.get_user_info_data(42, "mania") is user
        save_mode.assert_awaited_once_with(user, 3)
        save_mode.reset_mock()

        assert await api.get_user_info_data(42, "mania", update_snapshot=False) is user
        save_mode.assert_not_awaited()


@pytest.mark.asyncio
async def test_info_snapshot_store_batches_daily_rows_and_name_updates(after_nonebot_init):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_osubot.database.models import InfoData, UserData
    from nonebot_plugin_osubot.info.snapshot import SqlInfoSnapshotStore

    osu_id = 2_147_000_001
    user = SimpleNamespace(
        id=osu_id,
        username="new-name",
        badges=[],
        statistics_rulesets=SimpleNamespace(osu=_statistics(), taiko=None, fruits=None, mania=None),
    )

    async with get_session() as session:
        await session.execute(delete(InfoData).where(InfoData.osu_id == osu_id))
        await session.execute(delete(UserData).where(UserData.osu_id == osu_id))
        session.add_all(
            [
                UserData(user_id="snapshot-test-1", osu_id=osu_id, osu_name="old-name", osu_mode=0),
                UserData(user_id="snapshot-test-2", osu_id=osu_id, osu_name="old-name", osu_mode=3),
            ]
        )
        await session.commit()

    try:
        store = SqlInfoSnapshotStore()
        assert await store.save([user]) == 1
        user.statistics_rulesets.osu = _statistics(2345.6)
        assert await store.save([user]) == 1
        assert (
            await store.save_mode(
                SimpleNamespace(
                    id=osu_id,
                    username="mode-name",
                    badges=[],
                    statistics=_statistics(3456.7),
                ),
                3,
            )
            == 1
        )

        async with get_session() as session:
            snapshots = (
                await session.scalars(select(InfoData).where(InfoData.osu_id == osu_id).order_by(InfoData.osu_mode))
            ).all()
            bindings = (await session.scalars(select(UserData).where(UserData.osu_id == osu_id))).all()

        assert [snapshot.osu_mode for snapshot in snapshots] == [0, 1, 2, 3]
        assert snapshots[0].pp == pytest.approx(2345.6)
        assert snapshots[1].pp == 0
        assert snapshots[3].pp == pytest.approx(3456.7)
        assert {binding.osu_name for binding in bindings} == {"mode-name"}
    finally:
        async with get_session() as session:
            await session.execute(delete(InfoData).where(InfoData.osu_id == osu_id))
            await session.execute(delete(UserData).where(UserData.osu_id == osu_id))
            await session.commit()


@pytest.mark.asyncio
async def test_scheduled_info_update_uses_background_priority(after_nonebot_init):
    import nonebot_plugin_osubot as plugin
    from nonebot_plugin_osubot.network import scheduler as scheduler_module
    from nonebot_plugin_osubot.network.scheduler import RequestPriority

    session = AsyncMock()
    session.scalars = AsyncMock(return_value=[1, 2, 3])

    @asynccontextmanager
    async def fake_get_session():
        yield session

    priorities = []

    async def fake_update_users_info(user_ids: list[int]) -> int:
        priorities.append((user_ids, scheduler_module._current_priority.get()))
        return len(user_ids)

    with (
        patch.object(plugin, "get_session", fake_get_session),
        patch.object(plugin, "update_users_info", new=fake_update_users_info),
    ):
        await plugin.update_info()

    assert priorities == [([1, 2, 3], RequestPriority.BACKGROUND)]
