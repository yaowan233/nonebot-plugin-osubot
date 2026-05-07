"""
手动运行脚本，调用真实绘图函数并将结果保存到 tests/output/ 目录。

用法：
    uv run --dev python -m pytest tests/view_output.py -v -s

图片保存在 tests/output/
"""

import asyncio
import time
import pytest
from datetime import date, timedelta
from pathlib import Path
from nonebug import App

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

USERS = {
    "osu": (7562902, "osu"),
    "taiko": (31148838, "taiko"),
    "fruits": (7547506, "fruits"),
    "mania": (758406, "mania"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize(("mode_name", "uid", "mode"), [(name, uid, mode) for name, (uid, mode) in USERS.items()])
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
@pytest.mark.parametrize(("mode_name", "uid", "mode"), [(name, uid, mode) for name, (uid, mode) in USERS.items()])
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
@pytest.mark.parametrize(("mode_name", "uid", "mode"), [(name, uid, mode) for name, (uid, mode) in USERS.items()])
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


@pytest.mark.asyncio
async def test_recommend_real(app: App):
    """推荐 真实图片输出 (taiko)"""
    from nonebot_plugin_osubot.api import get_recommend
    from nonebot_plugin_osubot.draw.recommend import draw_recommend

    uid = 3162675
    mode = 1  # taiko

    t0 = time.perf_counter()
    print(f"\n  [recommend] 请求 API player_id={uid} mode=taiko ...")
    data = await get_recommend(uid, mode)
    print(f"  [recommend] 拿到 {len(data.recommendations or [])} 张谱面，渲染中...")
    pic = await draw_recommend(data, str(uid), f"https://a.ppy.sh/{uid}")
    elapsed = time.perf_counter() - t0
    path = OUT / "recommend_taiko.png"
    path.write_bytes(pic)
    print(f"  [recommend] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
async def test_recommend_stress(app: App):
    """压力测试：5 个用户多模式并发获取推荐"""
    from nonebot_plugin_osubot.api import get_recommend

    # (player_id, osu_mode_int, label)
    cases = [
        (3162675, 1, "taiko"),    # taiko player
        (124493, 0, "osu"),       # mrekk
        (4504101, 0, "osu"),      # WhiteCat
        (7562902, 0, "osu"),      # top osu player
        (31148838, 1, "taiko"),   # another taiko player
    ]

    results = []
    t0 = time.perf_counter()

    async def fetch(pid, mode, label):
        t1 = time.perf_counter()
        try:
            api_task = asyncio.create_task(get_recommend(pid, mode))
            done, _ = await asyncio.wait([api_task], timeout=5)
            waited = not done
            data = await api_task
            count = len(data.recommendations or [])
            t2 = time.perf_counter()
            print(f"  [{label}] pid={pid} -> {count} 张谱面, {t2-t1:.1f}s{' (需等待)' if waited else ''}")
            results.append((label, pid, count, t2 - t1, None))
        except Exception as e:
            t2 = time.perf_counter()
            print(f"  [{label}] pid={pid} -> 失败: {type(e).__name__}: {e}, {t2-t1:.1f}s")
            results.append((label, pid, 0, t2 - t1, str(e)))

    print(f"\n  [stress] 并发发送 {len(cases)} 个请求...")
    await asyncio.gather(*[fetch(pid, mode, label) for pid, mode, label in cases])

    total = time.perf_counter() - t0
    success = sum(1 for _, _, c, _, e in results if c > 0 and e is None)
    fail = sum(1 for _, _, _, _, e in results if e is not None)
    empty = sum(1 for _, _, c, _, e in results if c == 0 and e is None)
    print(f"\n  [stress] 总计: {total:.1f}s | 成功={success} | 空推荐={empty} | 失败={fail}")
    print(f"  [stress] 明细:")
    for label, pid, count, t, err in results:
        status = f"{count}张" if err is None else f"错误: {err[:40]}"
        print(f"    {label:>6}  pid={pid:>9}  {status:>20}  {t:.1f}s")
