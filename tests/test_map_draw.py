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
