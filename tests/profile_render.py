"""
成绩图（draw_score /bp1）渲染耗时 profile。

用法：
    uv run --dev python -m pytest tests/profile_render.py -q -s

对同一用户同一模式连跑 3 次：
  hot#1  热缓存第 1 次（含原生渲染器首次加载开销）
  hot#2  热缓存第 2 次（稳定态）
  cold   冷缓存（map/user/team 缓存目录重定向到临时目录，全部重新下载）

每个阶段输出累计秒数与占总耗时的比例。
注意：部分 API 调用是并发执行的（get_user_info_data 与 get_user_scores 等），
各阶段秒数是「墙钟累计」，加总可能超过总耗时，百分比仅供量级参考。
"""

import functools
import time
from collections import defaultdict

import pytest
from nonebug import App

UID, MODE = 7562902, "osu"

_timings = defaultdict(float)
_counts = defaultdict(int)


def _reset():
    _timings.clear()
    _counts.clear()


def _rec(name, dt):
    _timings[name] += dt
    _counts[name] += 1


def _wrap_async(fn, name):
    @functools.wraps(fn)
    async def wrapper(*a, **kw):
        t = time.perf_counter()
        try:
            return await fn(*a, **kw)
        finally:
            _rec(name, time.perf_counter() - t)

    return wrapper


def _wrap_sync(fn, name):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        t = time.perf_counter()
        try:
            return fn(*a, **kw)
        finally:
            _rec(name, time.perf_counter() - t)

    return wrapper


def _install_instrumentation(monkeypatch):
    import nonebot_plugin_osubot.draw.score as score_mod
    from osu_tools import OsuCalculator

    for name in (
        "get_user_scores",
        "get_user_info_data",
        "osu_api",
        "ensure_osu_file",
        "get_bg",
        "open_user_icon",
        "get_projectimg",
        "_owner_avatar_data",
        "_team_icon_data",
        "_cover_data_uri",
        "_player_avatar_data_uri",
        "render_score_svg",
        "draw_score_pic",
        "render_score_template",
    ):
        monkeypatch.setattr(score_mod, name, _wrap_async(getattr(score_mod, name), name))

    for name in ("cal_pp", "get_if_pp_ss_pp", "get_pp_components", "cal_score_info"):
        monkeypatch.setattr(score_mod, name, _wrap_sync(getattr(score_mod, name), name))

    monkeypatch.setattr(OsuCalculator, "calculate", _wrap_sync(OsuCalculator.calculate, "OsuCalculator.calculate"))

    return score_mod


_GROUPS = [
    ("网络 API", ["get_user_scores", "get_user_info_data", "osu_api", "ensure_osu_file"]),
    ("资源下载/读取", ["get_projectimg", "get_bg", "open_user_icon", "_owner_avatar_data", "_team_icon_data"]),
    ("PP 计算", ["cal_pp", "get_if_pp_ss_pp", "get_pp_components", "OsuCalculator.calculate"]),
    ("原生 SVG 出图", ["render_score_svg"]),
    ("骨架", ["draw_score_pic", "render_score_template", "cal_score_info"]),
]


def _report(label, wall):
    print(f"\n{'=' * 60}\n[{label}] 总耗时 {wall:.2f}s\n{'-' * 60}")
    accounted_groups = 0.0
    for group, names in _GROUPS:
        total = sum(_timings[n] for n in names)
        if total <= 0:
            continue
        accounted_groups += total
        print(f"  {group:<12} {total:7.2f}s  ({total / wall * 100:5.1f}%)")
        for n in names:
            if _timings[n] > 0:
                print(f"      {n:<32} {_timings[n]:7.2f}s  x{_counts[n]}")
    other = wall - sum(
        _timings[n]
        for group, names in _GROUPS
        for n in names
        if group not in {"骨架", "网络 API"}  # 骨架互相嵌套、API 互相并发，不计入
    )
    print(f"  {'其他(残差)':<12} {other:7.2f}s  ({other / wall * 100:5.1f}%)")


@pytest.mark.asyncio
async def test_profile_draw_score(app: App, monkeypatch, tmp_path):
    score_mod = _install_instrumentation(monkeypatch)

    async def run_once():
        t = time.perf_counter()
        await score_mod.draw_score(
            project="bp",
            uid=UID,
            is_lazer=True,
            mode=MODE,
            mods=[],
            search_condition=[],
            source="osu",
            best=1,
        )
        return time.perf_counter() - t

    wall = await run_once()
    _report("hot#1 热缓存第1次", wall)

    _reset()
    wall = await run_once()
    _report("hot#2 热缓存第2次", wall)

    _reset()
    import nonebot_plugin_osubot.file as file_mod
    import nonebot_plugin_osubot.draw.utils as utils_mod
    import nonebot_plugin_osubot.info.bg as bg_mod

    for mod in (file_mod, score_mod, utils_mod, bg_mod):
        monkeypatch.setattr(mod, "map_path", tmp_path / "map", raising=False)
        monkeypatch.setattr(mod, "user_cache_path", tmp_path / "user", raising=False)
        monkeypatch.setattr(mod, "team_cache_path", tmp_path / "team", raising=False)
    wall = await run_once()
    _report("cold 冷缓存(全部重新下载)", wall)


@pytest.mark.asyncio
async def test_profile_bmap(app: App, monkeypatch):
    import nonebot_plugin_osubot.api as api_mod
    import nonebot_plugin_osubot.draw.bmap as bmap_mod
    import nonebot_plugin_osubot.draw.map_render as map_render_mod

    local_timings = defaultdict(float)
    local_counts = defaultdict(int)

    def wrap_async(module, name):
        original = getattr(module, name)

        @functools.wraps(original)
        async def wrapper(*args, **kwargs):
            started = time.perf_counter()
            try:
                return await original(*args, **kwargs)
            finally:
                local_timings[name] += time.perf_counter() - started
                local_counts[name] += 1

        monkeypatch.setattr(module, name, wrapper)

    for module, name in (
        (api_mod, "_fetch_beatmapset"),
        (bmap_mod, "get_beatmapsets_info"),
        (bmap_mod, "_avatar_data_uri"),
        (bmap_mod, "beatmap_background_data_uri"),
        (bmap_mod, "render_map_template"),
        (map_render_mod, "get_bg"),
    ):
        wrap_async(module, name)

    async def run_once(label):
        local_timings.clear()
        local_counts.clear()
        started = time.perf_counter()
        await bmap_mod.draw_bmap_info(691220)
        wall = time.perf_counter() - started
        print(f"\n[bmap {label}] {wall:.3f}s")
        for name, elapsed in sorted(local_timings.items(), key=lambda item: item[1], reverse=True):
            print(f"  {name:<32} {elapsed:.3f}s x{local_counts[name]}")

    await run_once("cold-process")
    await run_once("hot")


@pytest.mark.asyncio
async def test_profile_map(app: App, monkeypatch):
    import nonebot_plugin_osubot.draw.map as map_mod
    import nonebot_plugin_osubot.draw.svg_render as svg_render_mod

    local_timings = defaultdict(float)
    local_counts = defaultdict(int)

    def wrap_async(name):
        original = getattr(map_mod, name)

        @functools.wraps(original)
        async def wrapper(*args, **kwargs):
            started = time.perf_counter()
            try:
                return await original(*args, **kwargs)
            finally:
                local_timings[name] += time.perf_counter() - started
                local_counts[name] += 1

        monkeypatch.setattr(map_mod, name, wrapper)

    def wrap_sync(name):
        original = getattr(map_mod, name)

        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                local_timings[name] += time.perf_counter() - started
                local_counts[name] += 1

        monkeypatch.setattr(map_mod, name, wrapper)

    for name in (
        "osu_api",
        "ensure_osu_file",
        "beatmap_background_data_uri",
        "cached_avatar_data_uri",
        "render_map_svg",
    ):
        wrap_async(name)
    for name in ("_ruleset_map", "get_ss_pp", "with_mods"):
        wrap_sync(name)

    original_svg_to_bytes = svg_render_mod.svg_to_bytes

    @functools.wraps(original_svg_to_bytes)
    def profiled_svg_to_bytes(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_svg_to_bytes(*args, **kwargs)
        finally:
            local_timings["svg_to_bytes"] += time.perf_counter() - started
            local_counts["svg_to_bytes"] += 1

    monkeypatch.setattr(svg_render_mod, "svg_to_bytes", profiled_svg_to_bytes)

    async def run_once(label):
        local_timings.clear()
        local_counts.clear()
        started = time.perf_counter()
        await map_mod.draw_map_info(1462799, ["HD", "DT"])
        wall = time.perf_counter() - started
        print(f"\n[map {label}] {wall:.3f}s")
        for name, elapsed in sorted(local_timings.items(), key=lambda item: item[1], reverse=True):
            print(f"  {name:<32} {elapsed:.3f}s x{local_counts[name]}")

    await run_once("cold-process")
    await run_once("hot")
