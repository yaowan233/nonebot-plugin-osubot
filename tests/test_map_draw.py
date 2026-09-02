import re
from types import SimpleNamespace


def test_nominations_resolve_related_user_names():
    from nonebot_plugin_osubot.draw.map import _nominations_text

    payload = {
        "current_nominations": [{"user_id": 1}, {"user_id": 2}],
        "related_users": [
            {"id": 1, "username": "First"},
            {"id": 2, "username": "Second"},
        ],
    }

    assert _nominations_text(payload) == "First / Second"


def test_mania_conversion_uses_converted_objects_and_forced_keys():
    from nonebot_plugin_osubot.draw.map import _apply_ruleset_metadata

    mapinfo = SimpleNamespace()
    ruleset_map = SimpleNamespace(
        cs=7.0,
        ar=9.0,
        od=8.0,
        hp=6.0,
        bpm=180.0,
        n_objects=300,
        n_circles=220,
        n_holds=80,
    )

    result = _apply_ruleset_metadata(mapinfo, ruleset_map, 3, ["4K"])

    assert result.mode_int == 3
    assert result.mode == "mania"
    assert result.cs == 4
    assert result.count_circles == 220
    assert result.count_sliders == 80
    assert result.count_spinners == 0


def test_taiko_conversion_uses_converted_object_counts():
    from nonebot_plugin_osubot.draw.map import _apply_ruleset_metadata

    mapinfo = SimpleNamespace()
    ruleset_map = SimpleNamespace(
        cs=4.0,
        ar=9.0,
        od=8.0,
        hp=6.0,
        bpm=180.0,
        n_circles=296,
        n_sliders=4,
        n_spinners=0,
    )

    result = _apply_ruleset_metadata(mapinfo, ruleset_map, 1, [])

    assert result.mode_int == 1
    assert result.mode == "taiko"
    assert result.count_circles == 296
    assert result.count_sliders == 4
    assert result.count_spinners == 0


def test_map_rating_distribution_with_only_zeroes_does_not_divide_by_zero():
    """没有任何评分的谱面不应生成越界的占位评分柱。"""
    from nonebot_plugin_osubot.draw.map_svg import _map_rating_and_failures

    payload = {
        "set": {},
        "map": {
            "rating": None,
            "rating_votes": 0,
            "rating_distribution": [0] * 11,
            "fail_points": [],
        },
    }

    svg = _map_rating_and_failures(payload)

    assert "暂无评分" in svg
    assert 'width="6" height="2" rx="2" fill="#f6b923"' not in svg


def test_map_failure_distribution_with_only_zeroes_does_not_divide_by_zero():
    """失败位置分布全为零时应按无数据渲染。"""
    from nonebot_plugin_osubot.draw.map_svg import _map_rating_and_failures

    payload = {
        "set": {},
        "map": {
            "rating": None,
            "rating_votes": 0,
            "rating_distribution": [],
            "fail_points": [0] * 100,
        },
    }

    svg = _map_rating_and_failures(payload)

    assert "失败位置分布" in svg
    assert "暂无数据" in svg
    assert 'width="7" height="2" rx="2"' not in svg


def test_map_rating_bars_stay_inside_rating_column():
    """评分柱不应越过评分区右侧的分隔线。"""
    from nonebot_plugin_osubot.draw.map_svg import _map_rating_and_failures

    payload = {
        "set": {},
        "map": {
            "rating": 7.5,
            "rating_votes": 55,
            "rating_distribution": list(range(11)),
            "fail_points": [],
        },
    }

    svg = _map_rating_and_failures(payload)
    rating_bar_x = [
        int(value)
        for value in re.findall(
            r'<rect x="(\d+)" y="[^"]+" width="6" height="[^"]+" rx="2" fill="#f6b923"/>',
            svg,
        )
    ]

    assert len(rating_bar_x) == 10
    assert max(x + 6 for x in rating_bar_x) < 205


def test_map_param_name_does_not_overlap_long_key():
    """长参数名 KEYS 与中文说明之间应保留足够间距。"""
    from nonebot_plugin_osubot.draw.map_svg import _map_params

    svg = _map_params(
        {
            "map": {
                "stats": [
                    {
                        "key": "KEYS",
                        "name": "键位数",
                        "before": 4.0,
                        "after": 4.0,
                    }
                ]
            }
        }
    )
    key = re.search(r'<text x="([^"]+)"[^>]*>KEYS</text>', svg)
    name = re.search(r'<text x="([^"]+)"[^>]*>键位数</text>', svg)

    assert key is not None
    assert name is not None
    assert float(name.group(1)) - float(key.group(1)) >= 40


def test_mania_map_hero_shows_ln_ratio_as_fifth_metric():
    from nonebot_plugin_osubot.draw.map_svg import _map_hero

    beatmap = {
        "mode_int": 3,
        "version": "4K",
        "stars": 4.63,
        "original_stars": 4.63,
        "ss_pp": 238.8,
        "bpm": 132,
        "duration": "4:06",
        "max_combo": 2132,
        "objects": 200,
        "sliders": 75,
    }

    mania_svg = _map_hero({"map": beatmap})
    std_svg = _map_hero({"map": {**beatmap, "mode_int": 0}})

    assert ">LN占比</text>" in mania_svg
    assert ">37.5%</text>" in mania_svg
    assert mania_svg.count('data-role="map-quick-metric"') == 5
    assert "LN占比" not in std_svg
    assert std_svg.count('data-role="map-quick-metric"') == 4
