"""
手动运行脚本，调用真实绘图函数并将结果保存到 tests/output/ 目录。

用法：
    uv run --dev python -m pytest tests/view_output.py -v -s

图片保存在 tests/output/
"""

import asyncio
import random
import time
import pytest
from datetime import date, timedelta
from pathlib import Path
from nonebug import App

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

DESIGN_ASSETS = Path(__file__).parent.parent / "design" / "score" / "assets"


def require_design_assets() -> None:
    """design/ 是本地素材目录，不随仓库分发；缺失时跳过依赖它的合成渲染测试。"""
    if not (DESIGN_ASSETS / "player-mrekk.png").exists():
        pytest.skip("design/ 素材目录不存在")


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
        is_lazer=True,
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
        is_lazer=True,
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
async def test_firsts_real(app: App):
    """玩家第一名成绩列表的真实 API 图片输出。"""
    from nonebot_plugin_osubot.draw import draw_bp

    uid, mode = USERS["osu"]
    t0 = time.perf_counter()
    data = await draw_bp(
        project="firsts",
        uid=uid,
        is_lazer=True,
        mode=mode,
        mods=[],
        low_bound=1,
        high_bound=10,
        day=0,
        search_condition=[],
        source="osu",
    )
    elapsed = time.perf_counter() - t0
    path = OUT / "firsts_osu.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [firsts] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
async def test_pfm_speed_change_preview(app: App):
    """基于真实 BP 数据预览非默认 DT 倍率标签。"""
    from nonebot_plugin_osubot.api import get_user_scores
    from nonebot_plugin_osubot.draw.bp import draw_pfm
    from nonebot_plugin_osubot.schema.score import Mod

    uid, mode = USERS["osu"]
    scores = await get_user_scores(uid, mode, "best", source="osu", legacy_only=False, limit=20)
    preview_scores = [score.model_copy(deep=True) for score in scores]

    def set_speed(score, rate: float):
        speed_mods = [mod for mod in score.mods if mod.acronym in {"DT", "NC", "HT"}]
        if not speed_mods:
            speed_mods = [Mod(acronym="DT")]
            score.mods.append(speed_mods[0])
        for mod in speed_mods:
            mod.settings = {**(mod.settings or {}), "speed_change": rate}

    set_speed(preview_scores[0], 1.2)
    set_speed(preview_scores[1], 1.5)
    data = await draw_pfm("bp", uid, preview_scores, preview_scores, mode, "osu", 1, 20, 0)
    path = OUT / "pfm_speed_change_preview.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [speed preview] -> {path.name}")


@pytest.mark.asyncio
async def test_bp1_speed_change_preview(app: App):
    """基于真实 BP1 数据预览单条成绩的非默认 DT 倍率标签。"""
    from nonebot_plugin_osubot.api import get_user_info_data, get_user_scores, osu_api
    from nonebot_plugin_osubot.draw.score import draw_score_pic
    from nonebot_plugin_osubot.schema.score import Mod

    uid, mode = USERS["osu"]
    score = (await get_user_scores(uid, mode, "best", source="osu", legacy_only=False, limit=1))[0]
    score = score.model_copy(deep=True)
    speed_mods = [mod for mod in score.mods if mod.acronym in {"DT", "NC", "HT"}]
    if not speed_mods:
        speed_mods = [Mod(acronym="DT")]
        score.mods.append(speed_mods[0])
    for mod in speed_mods:
        mod.settings = {**(mod.settings or {}), "speed_change": 1.2}

    info, map_json = await asyncio.gather(
        get_user_info_data(uid, mode, "osu"),
        osu_api("map", map_id=score.beatmap.id),
    )
    data = await draw_score_pic(score, info, map_json, "", "osu")
    path = OUT / "bp1_speed_change_preview.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [single speed preview] -> {path.name}")


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
async def test_info_without_badges_preview(app: App, monkeypatch):
    """使用真实玩家数据预览无近期荣誉时的 info 布局。"""
    import nonebot_plugin_osubot.draw.info as info_module

    original_get_user_info = info_module.get_user_info_data

    async def get_user_info_without_badges(*args, **kwargs):
        info = await original_get_user_info(*args, **kwargs)
        return info.model_copy(update={"badges": []}, deep=True)

    monkeypatch.setattr(info_module, "get_user_info_data", get_user_info_without_badges)
    uid, mode = USERS["fruits"]
    data = await info_module.draw_info(uid=uid, mode=mode, day=0, source="osu")
    path = OUT / "info_fruits_without_badges.jpg"
    path.write_bytes(data)
    print(f"\n  [fruits without badges] -> {path.name}")


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
        (3162675, 1, "taiko"),  # taiko player
        (124493, 0, "osu"),  # mrekk
        (4504101, 0, "osu"),  # WhiteCat
        (7562902, 0, "osu"),  # top osu player
        (31148838, 1, "taiko"),  # another taiko player
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
            print(f"  [{label}] pid={pid} -> {count} 张谱面, {t2 - t1:.1f}s{' (需等待)' if waited else ''}")
            results.append((label, pid, count, t2 - t1, None))
        except Exception as e:
            t2 = time.perf_counter()
            print(f"  [{label}] pid={pid} -> 失败: {type(e).__name__}: {e}, {t2 - t1:.1f}s")
            results.append((label, pid, 0, t2 - t1, str(e)))

    print(f"\n  [stress] 并发发送 {len(cases)} 个请求...")
    await asyncio.gather(*[fetch(pid, mode, label) for pid, mode, label in cases])

    total = time.perf_counter() - t0
    success = sum(1 for _, _, c, _, e in results if c > 0 and e is None)
    fail = sum(1 for _, _, _, _, e in results if e is not None)
    empty = sum(1 for _, _, c, _, e in results if c == 0 and e is None)
    print(f"\n  [stress] 总计: {total:.1f}s | 成功={success} | 空推荐={empty} | 失败={fail}")
    print("  [stress] 明细:")
    for label, pid, count, t, err in results:
        status = f"{count}张" if err is None else f"错误: {err[:40]}"
        print(f"    {label:>6}  pid={pid:>9}  {status:>20}  {t:.1f}s")


@pytest.mark.asyncio
async def test_bpa_synthetic_render(app: App):
    """bpa 合成数据渲染（不联网），用于查看图表样式"""
    from types import SimpleNamespace
    from nonebot_plugin_osubot.draw.echarts import build_bpa_data, draw_bpa_plot

    random.seed(42)
    ranks = ["XH", "X", "SH", "S", "A", "B", "C"]
    rank_weights = [0.05, 0.1, 0.08, 0.32, 0.3, 0.1, 0.05]
    mod_choices = [[], [], [], [("DT",)], [("HR", "HD")], [("HD",)], [("DT", "HD")], [("FL",)], [("EZ",)]]
    mapper_names = ["Sotarks", "Deru", "Monstrata", "Camellia", "Hollow Wings", "AJT", "olie", "gzdongsheng"]

    def _choose_mods():
        m = random.choice(mod_choices)
        return [SimpleNamespace(acronym=x) for x in m]

    score_ls = []
    base_pp = 580
    for i in range(75):
        decay = 0.95**i
        pp = max(60, base_pp * decay + random.uniform(-12, 12))
        r = random.choices(ranks, weights=rank_weights, k=1)[0]
        stars = max(3.5, min(9.5, 5.0 + (pp / base_pp) * 3.5 + random.uniform(-0.6, 0.6)))
        bpm = random.choice([160, 170, 180, 190, 200, 210, 220, 240, 260, 280])
        length = random.randint(90, 320)
        # DT 缩短时长
        mods = _choose_mods()
        is_dt = any(x.acronym in {"DT", "NC"} for x in mods)
        if is_dt:
            length = round(length / 1.5, 1)
        acc = max(92.0, min(99.9, 99.5 - (stars - 5) * 0.6 + random.uniform(-1.5, 1.0)))
        score_ls.append(
            SimpleNamespace(
                pp=round(pp, 1),
                rank=r,
                accuracy=round(acc, 2),
                ended_at=date(2022, 1, 1) + timedelta(days=i * 12),
                mods=mods,
                beatmap=SimpleNamespace(
                    total_length=length,
                    stars=round(stars, 2),
                    bpm=float(bpm),
                    user_id=1000 + (i % len(mapper_names)),
                    creator=mapper_names[i % len(mapper_names)],
                ),
            )
        )

    data = await build_bpa_data(score_ls, "ppysb")
    pic = await draw_bpa_plot(
        "TestPlayer osu 模式",
        username="TestPlayer",
        mode="osu",
        user_id=2,
        source="ppysb",
        **data,
    )
    path = OUT / "bpa_synthetic.png"
    path.write_bytes(pic)
    print(f"\n  [bpa synthetic] -> {path.name}  stats={data['stats']}")


@pytest.mark.asyncio
async def test_bpa_real_ctb(app: App):
    """bpa 真实数据渲染：3162675 fruits(ctb) 模式，并导出 JSON 快照"""
    import json
    from nonebot_plugin_osubot.api import get_user_scores
    from nonebot_plugin_osubot.draw.score import cal_score_info
    from nonebot_plugin_osubot.draw.echarts import build_bpa_data

    uid = 3162675
    mode = "fruits"

    t0 = time.perf_counter()
    score_ls = await get_user_scores(uid, mode, "best", "osu", legacy_only=True)
    print(f"\n  [bpa real ctb] 拿到 {len(score_ls)} 条 bp")
    if not score_ls:
        pytest.skip("没有拿到 bp 数据")

    for score in score_ls:
        score.mods = [mod for mod in score.mods if mod.acronym != "CL"]
        for mod in score.mods:
            if not score.beatmap:
                continue
            if mod.acronym in {"DT", "NC"}:
                score.beatmap.total_length = score.beatmap.total_length / 1.5
            if mod.acronym == "HT":
                score.beatmap.total_length = score.beatmap.total_length / 0.75

    score_ls = [cal_score_info(False, score) for score in score_ls]
    data = await build_bpa_data(score_ls, "osu")

    json_path = OUT / "bpa_real_ctb.json"
    json_path.write_text(json.dumps({"name": "3162675 fruits 模式", **data}, ensure_ascii=False), encoding="utf-8")
    print(f"  [bpa real ctb] JSON -> {json_path}")

    from nonebot_plugin_osubot.draw.echarts import draw_bpa_plot

    pic = await draw_bpa_plot(
        "3162675 fruits 模式",
        username="3162675",
        mode="fruits",
        user_id=uid,
        source="osu",
        **data,
    )
    elapsed = time.perf_counter() - t0
    path = OUT / "bpa_real_ctb.png"
    path.write_bytes(pic)
    print(f"  [bpa real ctb] {elapsed:.2f}s -> {path.name}  stats={data['stats']}")


@pytest.mark.asyncio
async def test_rank_synthetic(app: App):
    """群内排名场景：3 人自适应高度，以及 100 人的前三、前 20 与榜外本人。"""
    from nonebot_plugin_osubot.draw.rank import draw_group_rank

    require_design_assets()
    avatar_files = [
        DESIGN_ASSETS / "player-mrekk.png",
        *sorted((DESIGN_ASSETS / "collab").glob("mapper-*.png")),
    ]
    players = []
    for index in range(1, 101):
        players.append(
            {
                "osu_id": index,
                "osu_name": f"player_{index:03d}",
                "qq_name": f"群成员 {index:03d}",
                "avatar_url": avatar_files[(index - 1) % len(avatar_files)].as_uri(),
                "pp": 25_000 - index * 115.7,
                "global_rank": index * 893,
                "delta": None if index % 4 == 0 else index / 3,
            }
        )

    pic = await draw_group_rank(players, requester_osu_id=76, mode_name="标准模式", updated_at="2026/07/22 16:40")
    path = OUT / "rank_podium.png"
    path.write_bytes(pic)
    print(f"  [rank synthetic] -> {path.name}")

    small_pic = await draw_group_rank(
        players[:3],
        requester_osu_id=2,
        mode_name="标准模式",
        updated_at="2026/07/22 16:40",
    )
    small_path = OUT / "rank_small.png"
    small_path.write_bytes(small_pic)
    print(f"  [rank small] -> {small_path.name}")


def _rating_players() -> list[dict]:
    require_design_assets()
    avatar_files = [
        DESIGN_ASSETS / "player-mrekk.png",
        *sorted((DESIGN_ASSETS / "collab").glob("mapper-*.png")),
    ]
    names = ["Aster", "Kestrel", "Mikan", "Rin", "Yuzu", "Noir", "Sora", "Lumen"]
    players = []
    for index, name in enumerate(names):
        wins = 9 - index // 2
        losses = 3 + index // 2
        played = wins + losses
        players.append(
            {
                "user_id": index + 1,
                "name": name,
                "avatar": avatar_files[index % len(avatar_files)].as_uri(),
                "team": "red" if index % 2 == 0 else "blue",
                "rating": 2.34 - index * 0.11,
                "total_score": 8_920_000 - index * 417_000,
                "average_score": 743_333 - index * 22_500,
                "wins": wins,
                "losses": losses,
                "played": played,
                "win_rate": wins / played,
                "record_text": f"{wins}W—{losses}L · {wins / played:.1%}",
                "top1_count": max(0, 5 - index),
                "top1_rate": max(0, 5 - index) / played,
            }
        )
    return players


@pytest.mark.asyncio
@pytest.mark.parametrize("team_type", ["team-vs", "head-to-head"])
async def test_rating_synthetic(app: App, team_type: str):
    """多人评分正式模板：分别渲染团队赛与个人赛。"""
    from nonebot_plugin_osubot.draw.rating import draw_rating_card

    players = _rating_players()
    data = {
        "match_id": "1145141919",
        "title": "OSUBOT Summer Cup Finals",
        "time_range": "2026/07/22 19:30—21:08",
        "team_type": team_type,
        "algorithm": "OSUPLUS",
        "game_count": 12,
        "player_count": len(players),
        "players": players,
        "mvp": players[0],
        "max_top1_count": max(player["top1_count"] for player in players),
        "max_total_score": max(player["total_score"] for player in players),
        "average_rating": sum(player["rating"] for player in players) / len(players),
        "red_name": "Crimson Nova",
        "blue_name": "Azure Echo",
        "red_wins": 7,
        "blue_wins": 5,
        "red_players": [player for player in players if player["team"] == "red"],
        "blue_players": [player for player in players if player["team"] == "blue"],
        "team_size": 4,
    }
    pic = await draw_rating_card(data)
    path = OUT / f"rating_{team_type}.png"
    path.write_bytes(pic)
    print(f"  [rating {team_type}] -> {path.name}")


@pytest.mark.asyncio
@pytest.mark.parametrize("is_team", [True, False])
async def test_match_history_synthetic(app: App, is_team: bool):
    """多人战报正式模板：团队赛与窄版个人赛。"""
    from nonebot_plugin_osubot.draw.match_history import draw_match_card

    players = _rating_players()
    covers = [
        DESIGN_ASSETS / "beatmap-cover.jpg",
        DESIGN_ASSETS / "collab" / "cover.jpg",
    ]
    games = []
    for game_index in range(1, 4):
        rows = []
        for player_index, player in enumerate(players):
            score = 1_050_000 - player_index * 59_000 - game_index * 21_000
            if game_index == 3 and player["team"] == "blue":
                score += 170_000
            rows.append(
                {
                    "user_id": player["user_id"],
                    "name": player["name"],
                    "avatar": player["avatar"],
                    "team": player["team"],
                    "score": score,
                    "accuracy": 99.5 - player_index * 0.45,
                    "combo": 1_220 - player_index * 64,
                    "mods": [["HD"], ["HR"], ["DT"], [], ["HD", "HR"]][player_index % 5],
                }
            )
        rows.sort(key=lambda player: player["score"], reverse=True)
        red_players = [player for player in rows if player["team"] == "red"]
        blue_players = [player for player in rows if player["team"] == "blue"]
        red_score = sum(player["score"] for player in red_players)
        blue_score = sum(player["score"] for player in blue_players)
        games.append(
            {
                "index": game_index,
                "map_id": game_index,
                "title": ["Save Me", "Chronostasis", "The Pretender"][game_index - 1],
                "version": ["Nightmare", "Collab Extra", "Rebellion"][game_index - 1],
                "creator": "osu! community",
                "cover": covers[(game_index - 1) % 2].as_uri(),
                "stars": [6.42, 7.08, 6.76][game_index - 1],
                "winner": "red" if red_score > blue_score else "blue",
                "red_score": red_score,
                "blue_score": blue_score,
                "players": rows,
                "red_players": red_players,
                "blue_players": blue_players,
            }
        )
    data = {
        "match_id": "1145141919",
        "title": "OSUBOT Summer Cup Finals" if is_team else "Weekend Lobby",
        "team_type": "team-vs" if is_team else "head-to-head",
        "is_team": is_team,
        "red_name": "Crimson Nova",
        "blue_name": "Azure Echo",
        "red_wins": 2,
        "blue_wins": 1,
        "game_count": len(games),
        "player_count": len(players),
        "team_size": 4,
        "duration": "1h 38m",
        "time_range": "2026/07/22 19:30—21:08",
        "complete": True,
        "games": games,
    }
    pic = await draw_match_card(data)
    suffix = "team" if is_team else "h2h"
    path = OUT / f"match_history_{suffix}.png"
    path.write_bytes(pic)
    print(f"  [match history {suffix}] -> {path.name}")


@pytest.mark.asyncio
async def test_sl_real(app: App):
    """sl 谱面成绩列表 真实图片输出"""
    from nonebot_plugin_osubot.draw.score_history import draw_score_history

    t0 = time.perf_counter()
    data = await draw_score_history(7562902, True, "osu", [], 1475722, "osu")
    elapsed = time.perf_counter() - t0
    path = OUT / "sl_osu.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [sl osu] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
async def test_map_real(app: App):
    """map 单谱面信息真实图片输出"""
    from nonebot_plugin_osubot.draw.map import draw_map_info

    t0 = time.perf_counter()
    data = await draw_map_info(1462799, [])
    elapsed = time.perf_counter() - t0
    path = OUT / "map_osu.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [map osu] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
async def test_map_mod_real(app: App):
    """map 单谱面信息带 Mod 真实图片输出"""
    from nonebot_plugin_osubot.draw.map import draw_map_info

    t0 = time.perf_counter()
    data = await draw_map_info(1462799, ["HD", "DT"])
    elapsed = time.perf_counter() - t0
    path = OUT / "map_osu_hd_dt.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [map osu +HD+DT] {elapsed:.2f}s -> {path.name}")


@pytest.mark.asyncio
async def test_bmap_real(app: App):
    """bmap 谱面组信息 真实图片输出"""
    from nonebot_plugin_osubot.draw.bmap import draw_bmap_info

    t0 = time.perf_counter()
    data = await draw_bmap_info(691220)
    elapsed = time.perf_counter() - t0
    path = OUT / "bmap_osu.png"
    path.write_bytes(data.getvalue())
    print(f"\n  [bmap osu] {elapsed:.2f}s -> {path.name}")
