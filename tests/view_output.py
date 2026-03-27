"""
手动运行脚本，调用真实绘图函数并将结果保存到 tests/output/ 目录。

用法：
    uv run --dev python -m pytest tests/view_output.py -v -s

图片保存在 tests/output/
"""
import time
import pytest
from datetime import date, timedelta
from pathlib import Path
from nonebug import App

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

USERS = {
    "osu":    (7562902,  "osu"),
    "taiko":  (31148838, "taiko"),
    "fruits": (7547506,  "fruits"),
    "mania":  (758406,   "mania"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode_name,uid,mode", [
    (name, uid, mode) for name, (uid, mode) in USERS.items()
])
async def test_bp1_real(app: App, mode_name, uid, mode):
    """bp1 真实图片输出"""
    from nonebot_plugin_osubot.draw import draw_score

    t0 = time.perf_counter()
    data = await draw_score(
        project="bp",
        uid=uid,
        is_lazer=False,
        mode=mode,
        mods=[],
        search_condition=[],
        source="osu",
        best=1,
    )
    elapsed = time.perf_counter() - t0
    path = OUT / f"bp1_{mode_name}.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [{mode_name}] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode_name,uid,mode", [
    (name, uid, mode) for name, (uid, mode) in USERS.items()
])
async def test_pfm_real(app: App, mode_name, uid, mode):
    """pfm (bp1-20) 真实图片输出"""
    from nonebot_plugin_osubot.draw import draw_bp

    t0 = time.perf_counter()
    data = await draw_bp(
        project="bp",
        uid=uid,
        is_lazer=False,
        mode=mode,
        mods=[],
        low_bound=1,
        high_bound=20,
        day=0,
        search_condition=[],
        source="osu",
    )
    elapsed = time.perf_counter() - t0
    path = OUT / f"pfm_{mode_name}.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [{mode_name}] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode_name,uid,mode", [
    (name, uid, mode) for name, (uid, mode) in USERS.items()
])
async def test_info_real(app: App, mode_name, uid, mode):
    """info 真实图片输出"""
    from nonebot_plugin_osubot.draw import draw_info

    t0 = time.perf_counter()
    data = await draw_info(uid=uid, mode=mode, day=0, source="osu")
    elapsed = time.perf_counter() - t0
    path = OUT / f"info_{mode_name}.jpg"
    path.write_bytes(data)
    print(f"\n  [{mode_name}] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
async def test_info_extreme_changes(app: App):
    """info 极端变化值显示效果（超大正/负变化）"""
    from nonebot_plugin_osubot.draw import draw_info
    from nonebot_plugin_osubot.api import get_user_info_data
    from nonebot_plugin_osubot.database.models import InfoData
    from nonebot_plugin_osubot.utils import FGM
    from nonebot_plugin_orm import get_session

    uid, mode = USERS["osu"]
    info = await get_user_info_data(uid, mode, "osu")
    stats = info.statistics
    gc = stats.grade_counts

    old_date = date.today() - timedelta(days=30)
    old_record = InfoData(
        osu_id=info.id,
        osu_mode=FGM[mode],
        date=old_date,
        # 极端排名倒退
        c_rank=(stats.country_rank or 0) + 99999,
        g_rank=(stats.global_rank or 0) + 999999,
        # pp 大幅降低
        pp=max(0.0, stats.pp - 9999.99),
        acc=max(0.0, stats.hit_accuracy - 9.99),
        pc=max(0, stats.play_count - 99999),
        count=max(0, stats.total_hits - 9_999_999),
        ranked_score=max(0, stats.ranked_score - 99_999_999_999),
        total_score=max(0, stats.total_score - 999_999_999_999),
        max_combo=stats.maximum_combo,
        # 等级大幅减少
        count_xh=max(0, (gc.ssh or 0) - 999),
        count_x=max(0, (gc.ss or 0) - 9999),
        count_sh=max(0, (gc.sh or 0) - 999),
        count_s=max(0, (gc.s or 0) - 9999),
        count_a=max(0, (gc.a or 0) - 99999),
        replays=stats.replays_watched_by_others,
        play_time=max(0, (stats.play_time or 0) - 999_999),
        badge_count=0,
    )
    async with get_session() as session:
        session.add(old_record)
        await session.commit()

    t0 = time.perf_counter()
    data = await draw_info(uid=uid, mode=mode, day=30, source="osu")
    elapsed = time.perf_counter() - t0
    path = OUT / "info_osu_extreme_changes.jpg"
    path.write_bytes(data)
    print(f"\n  [extreme changes] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
async def test_info_with_changes(app: App):
    """info 变化值显示效果（osu 模式，插入7天前历史数据）"""
    from nonebot_plugin_osubot.draw import draw_info
    from nonebot_plugin_osubot.api import get_user_info_data
    from nonebot_plugin_osubot.database.models import InfoData
    from nonebot_plugin_osubot.utils import FGM
    from nonebot_plugin_orm import get_session

    uid, mode = USERS["osu"]

    # 获取当前真实数据
    info = await get_user_info_data(uid, mode, "osu")
    stats = info.statistics
    gc = stats.grade_counts

    # 插入一条「7天前」的历史记录，各项数值比当前低
    old_date = date.today() - timedelta(days=7)
    old_record = InfoData(
        osu_id=info.id,
        osu_mode=FGM[mode],
        date=old_date,
        c_rank=(stats.country_rank or 0) + 50,
        g_rank=(stats.global_rank or 0) + 500,
        pp=stats.pp - 50,
        acc=stats.hit_accuracy - 0.05,
        pc=stats.play_count - 30,
        count=stats.total_hits - 5000,
        ranked_score=stats.ranked_score - 1_000_000_000,
        total_score=stats.total_score - 2_000_000_000,
        max_combo=stats.maximum_combo,
        count_xh=(gc.ssh or 0) - 2,
        count_x=(gc.ss or 0) - 5,
        count_sh=(gc.sh or 0) - 3,
        count_s=(gc.s or 0) - 20,
        count_a=(gc.a or 0) - 50,
        replays=stats.replays_watched_by_others,
        play_time=(stats.play_time or 0) - 3600,
        badge_count=(len(info.badges) if info.badges else 0) - 1,
    )
    async with get_session() as session:
        session.add(old_record)
        await session.commit()

    t0 = time.perf_counter()
    data = await draw_info(uid=uid, mode=mode, day=7, source="osu")
    elapsed = time.perf_counter() - t0
    path = OUT / "info_osu_with_changes.jpg"
    path.write_bytes(data)
    print(f"\n  [osu with changes] {elapsed:.2f}s -> {path.name}")
