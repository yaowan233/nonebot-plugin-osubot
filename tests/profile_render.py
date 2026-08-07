"""
成绩图（draw_score /bp1）渲染耗时 profile。

用法：
    uv run --dev python -m pytest tests/profile_render.py -q -s

对同一用户同一模式连跑 3 次：
  hot#1  热缓存第 1 次（含浏览器首次拿页等冷启动开销）
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


_TIMED_PAGE_METHODS = {"set_content", "evaluate", "query_selector"}


class _TimedElement:
    def __init__(self, elem):
        self._elem = elem

    def __getattr__(self, name):
        attr = getattr(self._elem, name)
        if name == "screenshot":

            @functools.wraps(attr)
            async def timed(*a, **kw):
                t = time.perf_counter()
                try:
                    return await attr(*a, **kw)
                finally:
                    _rec("playwright: elem.screenshot", time.perf_counter() - t)

            return timed
        return attr


class _TimedPage:
    def __init__(self, page):
        self._page = page

    def __getattr__(self, name):
        attr = getattr(self._page, name)
        if name not in _TIMED_PAGE_METHODS:
            return attr

        @functools.wraps(attr)
        async def timed(*a, **kw):
            t = time.perf_counter()
            res = await attr(*a, **kw)
            _rec(f"playwright: page.{name}", time.perf_counter() - t)
            if name == "query_selector" and res is not None:
                return _TimedElement(res)
            return res

        return timed


class _TimedCM:
    def __init__(self, cm):
        self._cm = cm

    async def __aenter__(self):
        t = time.perf_counter()
        page = await self._cm.__aenter__()
        _rec("playwright: persistent_page(新建/复用)", time.perf_counter() - t)
        return _TimedPage(page)

    async def __aexit__(self, *args):
        return await self._cm.__aexit__(*args)


class _TimedTemplate:
    def __init__(self, template):
        self._template = template

    def __getattr__(self, name):
        attr = getattr(self._template, name)
        if name == "render_async":

            @functools.wraps(attr)
            async def timed(*a, **kw):
                t = time.perf_counter()
                try:
                    return await attr(*a, **kw)
                finally:
                    _rec("jinja 模板渲染", time.perf_counter() - t)

            return timed
        return attr


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
        "draw_score_pic",
        "render_score_template",
    ):
        monkeypatch.setattr(score_mod, name, _wrap_async(getattr(score_mod, name), name))

    for name in ("cal_pp", "get_if_pp_ss_pp", "get_pp_components", "cal_score_info"):
        monkeypatch.setattr(score_mod, name, _wrap_sync(getattr(score_mod, name), name))

    monkeypatch.setattr(OsuCalculator, "calculate", _wrap_sync(OsuCalculator.calculate, "OsuCalculator.calculate"))

    orig_persistent_page = score_mod.persistent_page

    def timed_persistent_page(*a, **kw):
        return _TimedCM(orig_persistent_page(*a, **kw))

    monkeypatch.setattr(score_mod, "persistent_page", timed_persistent_page)

    orig_env = score_mod.jinja2.Environment

    class TimedEnv(orig_env):
        def get_template(self, name, *a, **kw):
            return _TimedTemplate(super().get_template(name, *a, **kw))

    monkeypatch.setattr(score_mod.jinja2, "Environment", TimedEnv)

    return score_mod


_GROUPS = [
    ("网络 API", ["get_user_scores", "get_user_info_data", "osu_api", "ensure_osu_file"]),
    ("资源下载/读取", ["get_projectimg", "get_bg", "open_user_icon", "_owner_avatar_data", "_team_icon_data"]),
    ("PP 计算", ["cal_pp", "get_if_pp_ss_pp", "get_pp_components", "OsuCalculator.calculate"]),
    ("jinja 模板渲染", ["jinja 模板渲染"]),
    (
        "playwright 浏览器",
        [
            "playwright: persistent_page(新建/复用)",
            "playwright: page.set_content",
            "playwright: page.evaluate",
            "playwright: page.query_selector",
            "playwright: elem.screenshot",
        ],
    ),
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
