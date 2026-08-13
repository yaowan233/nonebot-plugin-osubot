import re
import time
from io import BytesIO
from types import SimpleNamespace

from PIL import Image
import pytest


def _image_uri(color: str = "#345678") -> str:
    import base64

    image = Image.new("RGB", (64, 64), color)
    output = BytesIO()
    image.save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def test_bp_svg_dynamic_height_and_team_alignment():
    from nonebot_plugin_osubot.draw.bp_svg import build_bp_svg

    payload = {
        "mode": "osu",
        "section_title": "最佳成绩",
        "range_label": "BP 1–1",
        "generated_at": "2026/01/01 00:00:00",
        "user": {
            "name": "player",
            "country": "CN",
            "support_level": 2,
            "avatar_data": _image_uri(),
            "team": {"short_name": "TEAM", "flag_data": _image_uri("#ff00aa")},
            "statistics": {"global_rank": 1, "pp": 1000},
        },
        "plays": [
            {
                "index": 1,
                "title": "Map",
                "artist": "Artist",
                "version": "Insane",
                "cover_data": _image_uri(),
                "pp": 100,
                "accuracy": 99,
                "stars": 5,
                "mods": [],
                "speed_changes": {},
                "date": "2026.01.01",
                "score_version": "lazer",
            }
        ],
    }

    svg, height = build_bp_svg(payload)

    assert height < 600
    assert 'x="182" y="116" width="31"' in svg
    assert "Lazer" in svg


def test_info_svg_restores_badge_cards_and_equal_grade_columns():
    from nonebot_plugin_osubot.draw.info_svg import build_info_svg
    from nonebot_plugin_osubot.draw.svg_render import text_width

    badge = {
        "image_data": _image_uri("#ff3f8e"),
        "description": "Tournament Champion",
        "awarded_at": "2026-01-01",
    }
    payload = {
        "id": 1,
        "username": "player",
        "country_code": "CN",
        "mode": "fruits",
        "badges": [badge] * 9,
        "statistics": {
            "level": {"current": 100, "progress": 50},
            "grade_counts": {"ssh": 1, "ss": 2, "sh": 3, "s": 4, "a": 5},
        },
    }

    svg = build_info_svg(payload)

    assert "最近 8 枚 / 共 9 枚" in svg
    assert 'data-role="info-bp-divider" x1="625" y1="671"' in svg
    assert 'width="118.875" height="55"' in svg
    assert 'id="info-badge-' not in svg
    for boundary in (136, 218, 300, 382):
        assert f'x1="{boundary}" y1="862" x2="{boundary}" y2="909"' in svg
    for rank in ("xh", "x", "sh", "s", "a"):
        assert f"rank-clip-{rank}-" in svg
    assert 'text-anchor="start" fill="#111824" opacity="1">90 天排名趋势</text>' in svg
    progress_x = max(135, 54 + text_width("100", 58) + 20)
    assert f'x="{progress_x}" y="758"' in svg
    assert '<polygon points="0,0 575,0 500,1140 0,1140"/>' in svg
    assert '<polygon points="562,0 586,0 511,1140 487,1140" fill="#ff3f8e"/>' in svg
    forbidden_neutral_text = {"#98a7ba", "#dce4ed", "#79879a", "#728196", "#77869a", "#697681", "#7d8791", "#65717d"}
    text_colors = set(re.findall(r'<text[^>]+fill="(#[0-9a-fA-F]{6})"', svg))
    assert text_colors.isdisjoint(forbidden_neutral_text)
    assert ">账号年龄</text>" in svg
    assert ">日均游玩</text>" in svg
    assert ">平均单次</text>" in svg


def test_info_svg_keeps_pp_unit_and_bp_shade_clear_of_content():
    from nonebot_plugin_osubot.draw.info_svg import build_info_svg
    from nonebot_plugin_osubot.draw.svg_render import text_width

    payload = {
        "id": 1,
        "username": "player",
        "country_code": "CN",
        "mode": "fruits",
        "statistics": {
            "global_rank": 3,
            "global_rank_percent": 0.000001,
            "country_rank": 2,
            "pp": 26_925.2,
            "level": {"current": 122, "progress": 63},
        },
        "best_plays": [{"rank": "X", "title": "Map", "stars": 10.3, "pp": 1601}],
    }

    svg = build_info_svg(payload)

    assert 'fill="#07111dbb"' not in svg
    assert 'id="info-bp-shade-0"' in svg
    assert 'stop-opacity="0"' in svg
    assert "近期荣誉" not in svg
    assert "暂无荣誉徽章" not in svg
    assert 'data-role="info-bp-divider" x1="625" y1="520"' in svg
    assert 'x1="635" y1="735" x2="831" y2="735" stroke="#c8ced1" stroke-dasharray="2 3"' in svg
    assert f'x="{1075 + text_width("26,925.2", 70) + 14}" y="193"' in svg
    assert 'data-gradient-start="#ffe600" data-gradient-end="#ed82ff"' in svg
    assert ">地区排名</text>" in svg
    assert ">CN #2</text>" in svg
    expected_bp_count_x = 635 + text_width("最佳成绩", 20) + 10
    assert f'x="{expected_bp_count_x}" y="551"' in svg


def test_bmap_svg_restores_difficulty_visuals_and_keeps_all_tags():
    from nonebot_plugin_osubot.draw.map_svg import MODE_GLYPHS, build_bmap_svg

    tags = "alpha beta gamma delta epsilon zeta eta theta final-tag"
    difficulty = {
        "id": 123,
        "mode": 0,
        "version": "Another",
        "length": "1:23",
        "stars": 5.2,
        "plays": 100,
        "passes": 42,
        "combo": 456,
        "cs": 4,
        "ar": 9,
        "od": 8,
        "hp": 6,
        "owners": [],
    }
    payload = {
        "set": {
            "id": 456,
            "title": "Map title",
            "artist": "Artist",
            "creator": "Mapper",
            "status": "ranked",
            "ranked_date": "2026.01.01",
            "source": "Source",
            "bpm": 180,
            "plays": 1000,
            "passes": 500,
            "favourites": 12,
            "duration": "2:34",
            "tags": tags,
        },
        "difficulties": [difficulty, {**difficulty, "id": 124, "stars": 7.1}],
        "show_difficulty_owners": False,
    }

    svg, height = build_bmap_svg(payload)

    assert height == 900
    assert 'data-role="title-card"' in svg
    assert 'data-role="title-card" x="436"' in svg
    assert 'clipPath id="bmap-title-card-clip"' in svg
    assert 'data-role="title-accent" x="436" y="61" width="8" height="130"' in svg
    assert 'clip-path="url(#bmap-title-card-clip)"' in svg
    assert 'id="bmap-spectrum-gradient"' in svg
    assert svg.count('data-role="spectrum-node"') == 2
    assert 'id="bmap-row-bg-0"' in svg
    assert 'id="bmap-row-bg-1"' in svg
    assert 'clipPath id="bmap-row-clip-0"' in svg
    assert 'data-role="difficulty-accent"' in svg
    assert 'clip-path="url(#bmap-row-clip-0)"' in svg
    assert svg.count('data-role="pass-progress"') == 2
    assert svg.count('data-role="difficulty-param"') == 8
    assert 'data-role="difficulty-param" x="1186"' in svg
    assert 'width="42" height="22" fill="#ffffff16"' in svg
    assert 'data-role="difficulty-param" x="1186" y="318" width="42" height="22" rx=' not in svg
    assert 'x="1207" y="333" font-family=' in svg
    assert 'text-anchor="middle"' in svg
    assert 'x="1186" y="290"' in svg
    assert 'x="926" y="315" width="76"' in svg
    assert 'x="1018" y="322"' in svg
    assert 'x="1108" y="320"' in svg
    assert 'data-font="extra"' in svg
    assert MODE_GLYPHS[0] in svg
    assert "final-tag" in svg


def test_map_svg_only_shows_star_change_card_for_actual_change_and_wraps_tags():
    from nonebot_plugin_osubot.draw.map_svg import build_map_svg

    payload = {
        "set": {
            "id": 456,
            "title": "Map title",
            "artist": "Artist",
            "creator": "Mapper",
            "status": "ranked",
            "ranked_date": "2026.01.01",
            "source": "Source",
            "favourites": 12,
            "tags": ["alpha", "beta", "gamma", "final-tag"],
        },
        "map": {
            "id": 123,
            "mode_int": 0,
            "version": "Another",
            "stars": 5.2,
            "original_stars": 5.2,
            "ss_pp": 123,
            "max_combo": 456,
            "bpm": 180,
            "duration": "2:34",
            "objects": 100,
            "circles": 30,
            "sliders": 60,
            "spinners": 10,
            "plays": 1000,
            "passes": 500,
            "mods": [],
            "stats": [
                {"key": key, "name": name, "before": value, "after": value}
                for key, name, value in (
                    ("CS", "圆圈大小", 4),
                    ("AR", "接近速度", 9),
                    ("OD", "判定难度", 8),
                    ("HP", "体力消耗", 6),
                )
            ],
            "object_labels": ("圆圈", "滑条", "转盘"),
        },
    }

    unchanged_svg, _height = build_map_svg(payload)

    assert 'data-role="star-change-card"' not in unchanged_svg
    assert 'data-role="map-stats-panel"><rect x="612" y="200"' in unchanged_svg
    assert ">谱面参数</text>" in unchanged_svg
    assert 'x1="720" y1="298.875" x2="1280" y2="298.875"' in unchanged_svg
    assert 'x="1355" y="304.875"' in unchanged_svg
    assert 'clipPath id="map-title-card-clip"' in unchanged_svg
    assert 'data-role="map-title-accent"' in unchanged_svg
    assert 'clip-path="url(#map-title-card-clip)"' in unchanged_svg
    assert 'data-role="object-composition"' in unchanged_svg
    assert '<rect x="720" y="616"' in unchanged_svg
    assert 'x="646" y="625"' in unchanged_svg
    assert 'x="1360" y="625"' in unchanged_svg
    assert 'data-role="map-tags"' in unchanged_svg
    assert "final-tag" in unchanged_svg

    payload["map"]["stars"] = 5.5
    payload["map"]["mods"] = ["HD", "HR"]
    changed_svg, _height = build_map_svg(payload)

    assert 'data-role="star-change-card"' not in changed_svg
    assert 'data-role="map-title-mods"' in changed_svg
    assert "模组后星数" not in changed_svg
    assert ">星数</text>" in changed_svg
    assert "菱形为模组后" not in changed_svg
    assert ">MODS</text>" not in changed_svg
    assert "5.50★" in changed_svg
    assert 'fill="#ff6b81" opacity="1">5.50★</text>' in changed_svg
    assert 'x="1299" y="140" width="28" height="28"' in changed_svg
    assert 'x="1332" y="140" width="28" height="28"' in changed_svg
    assert 'data-role="map-stats-panel"><rect x="612" y="200"' in changed_svg

    payload["map"]["stars"] = 5.0
    decreased_svg, _height = build_map_svg(payload)
    assert 'fill="#63d98b" opacity="1">5.00★</text>' in decreased_svg


@pytest.mark.parametrize(
    ("rank", "percent", "expected"),
    [
        (100, 0.5, ("#ffe600", "#ed82ff")),
        (101, 0.00049, ("#97dcff", "#ed82ff")),
        (1000, 0.00249, ("#d9f8d3", "#a0cf96")),
        (5000, 0.00499, ("#a8f0ef", "#52e0df")),
        (25_000, 0.0249, ("#f0e4a8", "#e0c952")),
        (50_000, 0.0499, ("#e0e0eb", "#a3a3c2")),
        (250_000, 0.249, ("#b88f7a", "#855c47")),
        (500_000, 0.499, ("#bab3ab", "#bab3ab")),
        (500_001, 0.5, ("#cccccc", "#999999")),
    ],
)
def test_info_global_rank_tier_colors(rank, percent, expected):
    from nonebot_plugin_osubot.draw.info_svg import _rank_colors

    assert _rank_colors({"global_rank": rank, "global_rank_percent": percent}) == expected


@pytest.mark.asyncio
@pytest.mark.no_cover
async def test_native_bp_raster_stays_inside_local_budget():
    from nonebot_plugin_osubot.draw.bp_svg import render_bp_svg
    from nonebot_plugin_osubot.draw.svg_render import warm_up_native_renderer

    play = {
        "index": 1,
        "title": "Map",
        "artist": "Artist",
        "version": "Insane",
        "cover_data": _image_uri(),
        "pp": 100,
        "accuracy": 99,
        "stars": 5,
        "mods": [],
        "speed_changes": {},
        "date": "2026.01.01",
        "score_version": "stable",
    }
    payload = {
        "mode": "osu",
        "section_title": "最佳成绩",
        "range_label": "BP 1–20",
        "generated_at": "2026/01/01 00:00:00",
        "user": {
            "name": "player",
            "country": "CN",
            "support_level": 0,
            "avatar_data": _image_uri(),
            "team": None,
            "statistics": {"global_rank": 1, "pp": 1000},
        },
        "plays": [{**play, "index": index + 1} for index in range(20)],
    }

    # Production performs this same warm-up in a background startup task. Keep
    # the budget focused on steady-state local rendering instead of import,
    # FreeType font loading, and the first resvg call.
    await warm_up_native_renderer()
    started = time.perf_counter()
    result = await render_bp_svg(payload)
    elapsed = time.perf_counter() - started

    with Image.open(result) as image:
        assert image.width == 1400
        assert image.height > 1000
    # A typical local run stays around 0.6s. GitHub's shared Linux runners can
    # take roughly twice as long inside native resvg, so keep enough headroom
    # for host variance while still catching meaningful regressions.
    assert elapsed < 1.5


def test_info_only_recalculates_stars_for_difficulty_mods():
    from nonebot_plugin_osubot.draw.info import _has_star_rating_mod

    assert _has_star_rating_mod(SimpleNamespace(mods=[SimpleNamespace(acronym="DT")]))
    assert _has_star_rating_mod(SimpleNamespace(mods=[SimpleNamespace(acronym="DA")]))
    assert not _has_star_rating_mod(SimpleNamespace(mods=[SimpleNamespace(acronym="HD")]))
    assert not _has_star_rating_mod(SimpleNamespace(mods=[SimpleNamespace(acronym="CL")]))
