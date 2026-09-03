from io import BytesIO
import xml.etree.ElementTree as ElementTree

import pytest
from PIL import Image


def _payload() -> dict:
    return {
        "name": "TestPlayer osu 模式",
        "username": "TestPlayer",
        "mode_label": "标准模式",
        "user_id": "2",
        "source_label": "ppy.sh",
        "avatar_data": None,
        "pp_ls": [500, 420, 360, 300, 250, 210, 180, 150, 125, 100, 80, 60],
        "length_ls": [{"value": 180}, {"value": 240}],
        "star_scatter": [
            {"name": "X", "data": [[7.2, 500], [6.5, 360]]},
            {"name": "S", "data": [[6.8, 420], [5.9, 300]]},
            {"name": "A", "data": [[5.4, 250], [4.9, 180]]},
        ],
        "mod_pp_ls": [{"name": "NM", "value": 1800}, {"name": "HD", "value": 900}],
        "mapper_pp_ls": [{"name": "Mapper A", "value": 1200}, {"name": "Mapper B", "value": 600}],
        "date_ls": ["2025-01-12", "2025-04-08", "2025-07-23", "2026-01-02"],
        "acc_ls": [97.2, 98.1, 98.7, 99.3],
        "bpm_ls": [175, 182, 190, 198, 205],
        "stats": {
            "weighted_pp": 3100.4,
            "total_pp": 3935,
            "bp_count": 12,
            "avg_acc": 98.33,
            "avg_stars": 6.12,
            "avg_bpm": 190,
            "top_mod": "NM",
        },
        "generated_on": "2026-09-03",
    }


def test_bpa_svg_contains_all_analysis_panels():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    svg = build_bpa_svg(_payload())

    for role in (
        "bpa-pp-curve",
        "bpa-grade",
        "bpa-star-efficiency",
        "bpa-mod-contribution",
        "bpa-mapper-preference",
        "bpa-time-distribution",
        "bpa-acc-distribution",
        "bpa-bpm-distribution",
    ):
        assert f'data-role="{role}"' in svg
    assert 'width="1620" height="1229"' in svg
    assert "TestPlayer" in svg
    assert "峰值 190–199 BPM · 2 张" in svg


def test_bpa_avatar_does_not_overlay_fallback_initial():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["avatar_data"] = "data:image/png;base64,avatar"

    root = ElementTree.fromstring(build_bpa_svg(payload))
    header = next(
        node for node in root.iter("{http://www.w3.org/2000/svg}g") if node.attrib.get("data-role") == "bpa-header"
    )
    fallback_initials = [
        node
        for node in header.iter("{http://www.w3.org/2000/svg}text")
        if node.attrib.get("x") == "93" and node.text == "T"
    ]

    assert fallback_initials == []


def test_bpa_avatar_shows_fallback_initial_without_image():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    root = ElementTree.fromstring(build_bpa_svg(_payload()))
    header = next(
        node for node in root.iter("{http://www.w3.org/2000/svg}g") if node.attrib.get("data-role") == "bpa-header"
    )
    fallback_initials = [
        node
        for node in header.iter("{http://www.w3.org/2000/svg}text")
        if node.attrib.get("x") == "93" and node.text == "T"
    ]

    assert len(fallback_initials) == 1


def test_bpa_time_axis_labels_are_evenly_spaced():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["date_ls"] = [f"{year}-{month:02d}-01" for year in (2024, 2025) for month in (1, 4, 7, 10)] + [
        "2026-01-01",
        "2026-04-01",
    ]

    root = ElementTree.fromstring(build_bpa_svg(payload))
    quarter_labels = [
        node
        for node in root.iter("{http://www.w3.org/2000/svg}text")
        if node.text and len(node.text) == 6 and node.text[:4].isdigit() and node.text[4] == "Q"
    ]
    positions = [float(node.attrib["x"]) for node in quarter_labels]
    gaps = [round(right - left, 2) for left, right in zip(positions, positions[1:])]

    assert len(quarter_labels) >= 5
    assert len(set(gaps)) == 1


def test_bpa_time_axis_preserves_empty_quarters():
    from nonebot_plugin_osubot.draw.bpa_svg import _quarter_histogram

    labels, counts = _quarter_histogram(["2024-01-01", "2024-07-01"])

    assert labels == ["2024Q1", "2024Q2", "2024Q3"]
    assert counts == [1, 0, 1]


def test_bpa_mod_names_share_a_left_aligned_column():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    root = ElementTree.fromstring(build_bpa_svg(_payload()))
    mod_group = next(
        node
        for node in root.iter("{http://www.w3.org/2000/svg}g")
        if node.attrib.get("data-role") == "bpa-mod-contribution"
    )
    mod_labels = [node for node in mod_group.iter("{http://www.w3.org/2000/svg}text") if node.text in {"NM", "HD"}]

    assert len(mod_labels) == 2
    assert len({node.attrib["x"] for node in mod_labels}) == 1
    assert {node.attrib["text-anchor"] for node in mod_labels} == {"start"}


def test_bpa_three_mod_rows_use_the_available_panel_height():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["mod_pp_ls"] = [
        {"name": "CL", "value": 8059.5},
        {"name": "DT", "value": 181.8},
        {"name": "NM", "value": 97.7},
    ]

    root = ElementTree.fromstring(build_bpa_svg(payload))
    mod_group = next(
        node
        for node in root.iter("{http://www.w3.org/2000/svg}g")
        if node.attrib.get("data-role") == "bpa-mod-contribution"
    )
    mod_labels = [
        node for node in mod_group.iter("{http://www.w3.org/2000/svg}text") if node.text in {"CL", "DT", "NM"}
    ]
    positions = sorted(float(node.attrib["y"]) for node in mod_labels)

    assert len(positions) == 3
    assert positions[-1] - positions[0] >= 120


@pytest.mark.parametrize(
    ("mod_count", "expected_height"),
    [(3, "32.00"), (4, "32.00"), (5, "24.80"), (6, "18.00"), (7, "16.00")],
)
def test_bpa_mod_bar_thickness_adapts_to_available_space(mod_count: int, expected_height: str):
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["mod_pp_ls"] = [
        {"name": name, "value": 1000 - index * 100}
        for index, name in enumerate(("CL", "DT", "NM", "HD", "HR", "EZ", "FL")[:mod_count])
    ]

    root = ElementTree.fromstring(build_bpa_svg(payload))
    mod_group = next(
        node
        for node in root.iter("{http://www.w3.org/2000/svg}g")
        if node.attrib.get("data-role") == "bpa-mod-contribution"
    )
    bar_heights = [
        node.attrib["height"]
        for node in mod_group.iter("{http://www.w3.org/2000/svg}rect")
        if node.attrib.get("height") in {"16.00", "18.00", "24.80", "32.00"}
    ]

    assert bar_heights == [expected_height] * mod_count


def test_bpa_mod_names_normalize_sequence_values():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["mod_pp_ls"] = [{"name": ("HD", "HR"), "value": 900}]

    svg = build_bpa_svg(payload)

    assert ">HD,HR</text>" in svg
    assert "('HD', 'HR')" not in svg


def test_bpa_curve_uses_a_local_pp_scale_for_a_tight_range():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["pp_ls"] = [473 - 221 * index / 199 for index in range(200)]

    root = ElementTree.fromstring(build_bpa_svg(payload))
    curve_group = next(
        node for node in root.iter("{http://www.w3.org/2000/svg}g") if node.attrib.get("data-role") == "bpa-pp-curve"
    )
    y_labels = [
        node.text for node in curve_group.iter("{http://www.w3.org/2000/svg}text") if float(node.attrib["x"]) == 105
    ]

    assert y_labels == ["500", "450", "400", "350", "300", "250"]


def test_bpa_histogram_uses_readable_integer_ticks():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["acc_ls"] = [97.1] * 5 + [97.6] * 10 + [98.1] * 20 + [98.6] * 50 + [99.1] * 70 + [99.6] * 60

    root = ElementTree.fromstring(build_bpa_svg(payload))
    acc_group = next(
        node
        for node in root.iter("{http://www.w3.org/2000/svg}g")
        if node.attrib.get("data-role") == "bpa-acc-distribution"
    )
    y_labels = [
        node.text for node in acc_group.iter("{http://www.w3.org/2000/svg}text") if float(node.attrib["x"]) == 601
    ]

    assert y_labels == ["80", "60", "40", "20", "0"]


def test_bpa_star_efficiency_keeps_both_axis_scales():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    root = ElementTree.fromstring(build_bpa_svg(_payload()))
    star_group = next(
        node
        for node in root.iter("{http://www.w3.org/2000/svg}g")
        if node.attrib.get("data-role") == "bpa-star-efficiency"
    )
    left_ticks = [
        node for node in star_group.iter("{http://www.w3.org/2000/svg}text") if float(node.attrib["x"]) == 106
    ]
    right_ticks = [
        node for node in star_group.iter("{http://www.w3.org/2000/svg}text") if float(node.attrib["x"]) == 528
    ]

    assert len(left_ticks) >= 4
    assert len(right_ticks) >= 4


def test_bpa_mod_contribution_hides_values_rounded_to_zero():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["mod_pp_ls"] = [{"name": "CL", "value": 100}, {"name": "HR", "value": 0.02}]

    root = ElementTree.fromstring(build_bpa_svg(payload))
    mod_group = next(
        node
        for node in root.iter("{http://www.w3.org/2000/svg}g")
        if node.attrib.get("data-role") == "bpa-mod-contribution"
    )
    values = [node.text for node in mod_group.iter("{http://www.w3.org/2000/svg}text")]

    assert "CL" in values
    assert "HR" not in values


def test_bpa_header_keeps_the_mode_icon():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    payload["mode_icon"] = "\ue801"

    svg = build_bpa_svg(payload)

    assert 'data-role="bpa-mode-icon"' in svg
    assert 'data-font="extra"' in svg


def test_bpa_svg_handles_empty_distributions():
    from nonebot_plugin_osubot.draw.bpa_svg import build_bpa_svg

    payload = _payload()
    for key in ("pp_ls", "star_scatter", "mod_pp_ls", "mapper_pp_ls", "date_ls", "acc_ls", "bpm_ls"):
        payload[key] = []

    svg = build_bpa_svg(payload)

    assert svg.count("暂无数据") == 7
    assert "BP#1 → #0" in svg


@pytest.mark.asyncio
async def test_bpa_svg_raster_smoke():
    from nonebot_plugin_osubot.draw.bpa_svg import render_bpa_svg

    result = await render_bpa_svg(_payload())

    assert isinstance(result, BytesIO)
    with Image.open(result) as rendered:
        assert rendered.format == "JPEG"
        assert rendered.size == (1620, 1229)


@pytest.mark.asyncio
async def test_draw_bpa_plot_delegates_to_native_renderer(monkeypatch):
    from nonebot_plugin_osubot.draw import echarts

    async def fake_avatar(*_args, **_kwargs):
        return "data:image/jpeg;base64,avatar"

    async def fake_render(data):
        assert data["username"] == "TestPlayer"
        assert data["mode_label"] == "标准模式"
        assert data["avatar_data"] == "data:image/jpeg;base64,avatar"
        return BytesIO(b"native-bpa")

    assert not hasattr(echarts, "_render_chart_template")
    monkeypatch.setattr(echarts, "image_source_data_uri", fake_avatar)
    monkeypatch.setattr(echarts, "render_bpa_svg", fake_render)

    result = await echarts.draw_bpa_plot(
        "TestPlayer osu 模式",
        _payload()["pp_ls"],
        _payload()["length_ls"],
        _payload()["star_scatter"],
        _payload()["mod_pp_ls"],
        _payload()["mapper_pp_ls"],
        _payload()["stats"],
        username="TestPlayer",
        mode="osu",
        user_id=2,
    )

    assert result == b"native-bpa"
