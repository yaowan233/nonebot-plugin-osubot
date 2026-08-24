import importlib
import json
import time
from html import escape
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image


@pytest.fixture
def api_module(after_nonebot_init):
    module = importlib.import_module("nonebot_plugin_osubot.api")
    module._achievements_cache.clear()
    yield module
    module._achievements_cache.clear()


@pytest.fixture
def medal_module(after_nonebot_init):
    return importlib.import_module("nonebot_plugin_osubot.matcher.medal")


@pytest.mark.asyncio
async def test_catalog_prefers_online_source_over_disk(api_module):
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "content": [
                {
                    "Medal_ID": 1,
                    "Name": "Online Medal",
                    "Link": "online.png",
                    "Gamemode": "osu",
                    "Packs": "T1",
                    "Solution": "Online solution",
                }
            ]
        },
    )

    with (
        patch.object(api_module, "safe_async_get", new=AsyncMock(return_value=response)) as request,
        patch.object(api_module, "load_achievements_catalog_disk", return_value=[{"id": 2, "name": "Disk"}]) as disk,
        patch.object(api_module, "_save_achievements_disk"),
    ):
        catalog = await api_module.fetch_achievements_catalog(force=True)

    assert catalog[0]["name"] == "Online Medal"
    assert catalog[0]["pack_id"] == "T1"
    assert catalog[0]["solution"] == "Online solution"
    request.assert_awaited_once()
    disk.assert_not_called()


@pytest.mark.asyncio
async def test_catalog_falls_back_to_disk_after_both_online_sources_fail(api_module):
    disk_catalog = [{"id": 2, "name": "Disk Medal"}]

    with (
        patch.object(api_module, "safe_async_get", new=AsyncMock(side_effect=[None, None])) as request,
        patch.object(api_module, "load_achievements_catalog_disk", return_value=disk_catalog) as disk,
    ):
        catalog = await api_module.fetch_achievements_catalog(force=True)

    assert catalog == disk_catalog
    assert request.await_count == 2
    disk.assert_called_once_with()


@pytest.mark.asyncio
async def test_catalog_uses_profile_html_before_disk(api_module):
    payload = {
        "achievements": [
            {
                "id": 3,
                "name": "Profile Medal",
                "slug": "profile-medal",
                "icon_url": "https://example.com/profile.png",
                "grouping": "Skill",
                "mode": "mania",
            }
        ]
    }
    html_response = SimpleNamespace(
        status_code=200,
        text=f'<div data-initial-data="{escape(json.dumps(payload), quote=True)}"></div>',
    )

    with (
        patch.object(api_module, "safe_async_get", new=AsyncMock(side_effect=[None, html_response])) as request,
        patch.object(api_module, "load_achievements_catalog_disk") as disk,
        patch.object(api_module, "_save_achievements_disk"),
    ):
        catalog = await api_module.fetch_achievements_catalog(force=True)

    assert catalog[0]["name"] == "Profile Medal"
    assert request.await_count == 2
    disk.assert_not_called()


@pytest.mark.asyncio
async def test_catalog_reuses_fresh_memory_cache(api_module):
    cached = [{"id": 1, "name": "Cached Medal"}]
    api_module._achievements_cache.update({"fetched_at": time.time(), "achievements": cached})

    with patch.object(api_module, "safe_async_get", new=AsyncMock()) as request:
        assert await api_module.fetch_achievements_catalog() == cached

    request.assert_not_awaited()


def test_myach_mode_filter_keeps_global_and_selected_mode(medal_module):
    achievements = [
        {"id": 1, "mode": None},
        {"id": 2, "mode": "taiko"},
        {"id": 3, "mode": "mania"},
    ]

    assert medal_module._filter_achievements_by_mode(achievements, "taiko") == achievements[:2]


def test_recommendations_prefer_chinese_and_fall_back_to_english(medal_module):
    with patch.dict(
        medal_module.medal_json,
        {"Chinese": {"MedalSolution": "中文攻略"}, "English": {"MedalSolution": ""}},
        clear=True,
    ):
        assert (
            medal_module._get_recommendation_solution({"id": 1, "name": "Chinese", "instructions": "Chinese source"})
            == "中文攻略"
        )
        assert (
            medal_module._get_recommendation_solution(
                {"id": 2, "name": "English", "instructions": "<i>English guide</i>"}
            )
            == "暂无中文攻略，英文原文：English guide"
        )
        assert medal_module._get_recommendation_solution({"id": 3, "name": "Missing"}) == "暂无可用攻略"


def test_md_preserves_pack_and_related_beatmap_metadata(medal_module):
    achievement = {"id": 1, "name": "Pack Medal", "pack_id": "T1,T2"}
    local_detail = {"BeatmapID": "11,22,33"}

    assert medal_module._pack_urls(achievement, local_detail) == [
        "https://osu.ppy.sh/beatmaps/packs/T1",
        "https://osu.ppy.sh/beatmaps/packs/T2",
    ]
    assert medal_module._related_beatmaps(achievement, local_detail) == [{"id": "11"}, {"id": "22"}, {"id": "33"}]


def test_strip_medal_html_handles_multiple_tables_scripts_and_entities(medal_module):
    value = (
        "<TABLE><TR><TD>One</TD></TR></TABLE><table><tr><td>Two</td></tr></table><SCRIPT>alert('x')</SCRIPT>&amp; done"
    )

    result = medal_module._strip_medal_html(value)

    assert "One" in result
    assert "Two" in result
    assert "alert" not in result
    assert "& done" in result


@pytest.mark.asyncio
async def test_achievement_grid_renders(after_nonebot_init, monkeypatch):
    from nonebot_plugin_osubot.draw import browser
    from nonebot_plugin_osubot.draw.medal import draw_achievements

    monkeypatch.setattr(browser._render_scheduler, "_render_timeout", 30)
    pixel = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
    image = await draw_achievements(
        {
            "me_name": "UID 1",
            "me_avatar": pixel,
            "title": "已获得成就",
            "subtitle": "共 1 个成就 · OSU",
            "total": 1,
            "start": 1,
            "end": 1,
            "achievements": [
                {
                    "name": "500 Combo",
                    "icon": pixel,
                    "grouping": "Skill & Dedication",
                    "achieved_at": "2026-08-24",
                }
            ],
        }
    )

    with Image.open(BytesIO(image)) as rendered:
        assert rendered.width == 1280 * 2
        assert rendered.height >= 900 * 2
