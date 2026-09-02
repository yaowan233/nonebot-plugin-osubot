import statistics
import time
import xml.etree.ElementTree as ElementTree
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
import pytest


def test_fit_text_shrinks_long_labels():
    from nonebot_plugin_osubot.draw.svg_render import fit_text

    assert fit_text("short", 500, 54, 30) == 54
    assert fit_text("A very long beatmap title that cannot fit the slot", 300, 54, 30) < 54


def test_score_svg_long_metadata_stays_inside_its_slots():
    from nonebot_plugin_osubot.draw.score_svg import _render_identity, _render_map_strip
    from nonebot_plugin_osubot.draw.svg_render import text_width

    title = "Denial // Rebirth " * 8
    artist = "Crystal Lake and an Extremely Long Featured Artist Name"
    version = "Emptiness Within Finally Yielding to a Fierce New Vision"
    team_name = "Furry Gaming International Championship Division"
    map_data = {"title": title, "artist": artist, "version": version, "stars": "14.76"}
    map_root = ElementTree.fromstring(f"<svg>{_render_map_strip(map_data)}</svg>")
    map_texts = list(map_root.iter("text"))
    title_node = next(node for node in map_texts if node.attrib["y"] == "151")
    artist_node = next(node for node in map_texts if node.attrib["x"] == "368" and node.attrib["y"] == "186")
    version_node = next(node for node in map_texts if node.attrib["y"] == "183")
    star_rect = next(node for node in map_root.iter("rect") if node.attrib.get("y") == "122")
    version_rect = next(node for node in map_root.iter("rect") if node.attrib.get("y") == "164")

    rendered_title = title_node.text or ""
    rendered_version = version_node.text or ""
    assert rendered_title.endswith("…")
    assert text_width(rendered_title, int(title_node.attrib["font-size"])) <= (
        float(star_rect.attrib["x"]) - float(title_node.attrib["x"]) - 12
    )
    rendered_artist = artist_node.text or ""
    assert rendered_artist.endswith("…")
    assert text_width(rendered_artist, int(artist_node.attrib["font-size"])) <= 285
    assert rendered_version.endswith("…")
    assert text_width(rendered_version, int(version_node.attrib["font-size"])) <= (
        float(version_rect.attrib["width"]) - 22
    )

    identity_root = ElementTree.fromstring(
        f"<svg>{_render_identity({'username': 'KayotoRahn', 'team': {'short_name': 'FUR', 'name': team_name}})}</svg>"
    )
    team_node = next(node for node in identity_root.iter("text") if node.attrib.get("y") == "708")
    rendered_team = team_node.text or ""
    assert rendered_team.endswith("…")
    assert text_width(rendered_team, int(team_node.attrib["font-size"])) <= 244


def test_render_svg_jpeg_uses_requested_size():
    from nonebot_plugin_osubot.draw.svg_render import FONT_FAMILY, render_svg_jpeg

    result = render_svg_jpeg(
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180">'
        '<rect width="320" height="180" fill="#111925"/>'
        f'<text x="20" y="60" font-family="{FONT_FAMILY}" font-size="24" fill="white">中文 yg</text>'
        "</svg>",
        width=320,
        height=180,
    )

    assert isinstance(result, BytesIO)
    with Image.open(result) as image:
        assert image.format == "JPEG"
        assert image.size == (320, 180)
        assert image.convert("L").getextrema()[1] > 100


def test_render_svg_jpeg_composites_external_background():
    import base64

    from nonebot_plugin_osubot.draw.svg_render import render_svg_jpeg

    source = BytesIO()
    Image.new("RGB", (80, 80), "#2468a0").save(source, "JPEG")
    background = f"data:image/jpeg;base64,{base64.b64encode(source.getvalue()).decode()}"
    result = render_svg_jpeg(
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">'
        '<rect x="20" y="20" width="40" height="40" fill="#ff4060"/>'
        "</svg>",
        width=80,
        height=80,
        background_data_uri=background,
    )

    with Image.open(result) as image:
        assert image.getpixel((5, 5))[2] > image.getpixel((5, 5))[0]
        assert image.getpixel((40, 40))[0] > image.getpixel((40, 40))[2]


def test_thumbnail_data_uri_merges_concurrent_generation(tmp_path):
    from nonebot_plugin_osubot.draw.svg_render import thumbnail_data_uri

    source = tmp_path / "cover.jpg"
    Image.new("RGB", (900, 250), "#345678").save(source, "JPEG")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _index: thumbnail_data_uri(source, max_width=320, max_height=180), range(8)))

    assert len(set(results)) == 1
    assert (tmp_path / "cover.card-320x180-q84.jpg").exists()


@pytest.mark.asyncio
async def test_native_score_renderer_preserves_text_and_bundled_images():
    from nonebot_plugin_osubot.draw.score_svg import build_score_svg, render_score_svg
    from nonebot_plugin_osubot.draw.score import _png_file_data_uri
    from nonebot_plugin_osubot.draw.static import osufile

    cover = Image.new("RGB", (640, 360), "#244466")
    avatar = Image.new("RGBA", (64, 64), "#44ddaa")
    cover_io = BytesIO()
    avatar_io = BytesIO()
    cover.save(cover_io, "JPEG")
    avatar.save(avatar_io, "PNG")
    import base64

    data_uri = lambda mime, raw: f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"
    data = {
        "title": "中文 Test",
        "artist": "Artist",
        "version": "Insane",
        "cover": data_uri("jpeg", cover_io.getvalue()),
        "avatar": data_uri("png", avatar_io.getvalue()),
        "rank_image": _png_file_data_uri(osufile / "ranking" / "legacy-ranking-S@2x.png"),
        "mods": [
            {"name": "DT", "speed_change": "1.30×"},
            {"name": "HD", "speed_change": None},
            {"name": "NM", "speed_change": None},
        ],
        "owners": [],
        "judgements": [],
        "dimensions": [],
        "pp_components": [],
        "pp_targets": [],
        "stars": "5.00",
        "score": "1,234,567",
    }

    svg = build_score_svg(data)
    assert 'data-role="mod-settings"' in svg
    assert 'width="50.625" height="36"' in svg
    assert '<rect x="44" y="80" width="300" height="180" rx="15"' in svg
    assert '<rect x="44" y="618" width="1352" height="256" rx="18"' in svg
    assert ">NM</text>" not in svg

    result = await render_score_svg(data)

    with Image.open(result) as image:
        assert image.format == "JPEG"
        assert image.size == (1440, 900)
        # The refined layout keeps the rank at right, the map strip at top-left,
        # and the official mod strip directly after the star pill.
        assert image.crop((1040, 160, 1370, 510)).convert("L").getextrema()[1] > 150
        assert image.crop((250, 110, 700, 225)).convert("L").getextrema()[1] > 150
        rate_region = image.crop((430, 120, 800, 165)).convert("RGB")
        assert any(
            red > 170 and red > green * 1.35
            for y in range(rate_region.height)
            for x in range(rate_region.width)
            for red, green, _blue in (rate_region.getpixel((x, y)),)
        )


def test_mania_score_judgements_show_yellow_rainbow_ratio():
    from nonebot_plugin_osubot.draw.score_svg import _render_judgements

    mania_svg = _render_judgements(
        {
            "ratio": "12.5 : 1",
            "judge_cols": 3,
            "judgements": [
                {"label": "MAX / 彩 300", "value": 1250, "display": "1,250"},
                {"label": "300", "value": 100, "display": "100"},
            ],
        }
    )

    assert 'data-role="mania-ratio"' in mania_svg
    assert ">黄彩比 12.5 : 1</text>" in mania_svg
    assert 'data-role="mania-ratio"' not in _render_judgements({"ratio": None})


def test_mania_score_map_strip_shows_ln_ratio_only_for_mania():
    from nonebot_plugin_osubot.draw.score_svg import _render_map_strip

    data = {
        "mode_code": "MANIA",
        "title": "Map",
        "artist": "Artist",
        "version": "4K",
        "stars": "4.63",
        "bpm": "132",
        "objects": "2,119",
        "length": "4:06",
        "map_id": 5856294,
        "dimensions": [{"name": "KEYS", "current": "4"}],
        "ln_ratio": "37.5%",
    }

    mania_svg = _render_map_strip(data)

    assert ">LN占比: </text>" in mania_svg
    assert ">37.5%</text>" in mania_svg
    assert "LN占比" not in _render_map_strip({**data, "mode_code": "STD"})


def test_score_atmosphere_has_no_visible_column_seams():
    """Cached background ambience must remain continuous across the canvas."""
    from nonebot_plugin_osubot.draw.score_svg import HEIGHT, WIDTH, _atmosphere_rgba

    atmosphere = Image.frombytes("RGBA", (WIDTH, HEIGHT), _atmosphere_rgba())
    background = Image.new("RGBA", (WIDTH, HEIGHT), "#587080")
    background.alpha_composite(atmosphere)
    column_colours = list(background.convert("RGB").resize((WIDTH // 4, 1), Image.Resampling.BOX).get_flattened_data())
    jumps = [
        (
            sum(abs(previous - current) for previous, current in zip(column_colours[x - 1], column_colours[x])),
            x * 4,
        )
        for x in range(1, len(column_colours))
    ]

    assert max(jumps)[0] <= 3, max(jumps)


@pytest.mark.asyncio
@pytest.mark.no_cover
async def test_native_score_raster_stays_inside_local_budget():
    """Keep the refined score layout inside the documented hot-path budget."""
    import base64

    from nonebot_plugin_osubot.draw.score_svg import (
        _atmosphere_rgba,
        _background_jpeg,
        render_score_svg,
    )
    from nonebot_plugin_osubot.draw.svg_render import warm_up_native_renderer

    cover = BytesIO()
    avatar = BytesIO()
    Image.new("RGB", (640, 360), "#244466").save(cover, "JPEG")
    Image.new("RGBA", (64, 64), "#44ddaa").save(avatar, "PNG")

    def data_uri(mime: str, raw: bytes) -> str:
        return f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"

    cover_uri = data_uri("jpeg", cover.getvalue())
    avatar_uri = data_uri("png", avatar.getvalue())
    data = {
        "mode_code": "STD",
        "ended_at": "2026.01.25 03:06:43",
        "status": "RANKED",
        "score_version": "lazer",
        "title": "Crystalia",
        "artist": "DJ TOTTO",
        "version": "Meal's Ultra",
        "cover": cover_uri,
        "avatar": avatar_uri,
        "rank_image": avatar_uri,
        "mods": [{"name": "HD"}, {"name": "DT", "speed_change": "1.50x"}],
        "owners": [{"username": f"Mapper {index}", "avatar": avatar_uri} for index in range(20)],
        "dimensions": [
            {"name": "CS", "current": "3.3", "current_pos": 30, "changed": False},
            {"name": "AR", "current": "10.6", "current_pos": 96.4, "changed": True},
            {"name": "OD", "current": "10.8", "current_pos": 98.2, "changed": True},
            {"name": "HP", "current": "6.0", "current_pos": 54.5, "changed": False},
        ],
        "judgements": [
            {"label": "300", "value": 551, "display": "551"},
            {"label": "100", "value": 22, "display": "22"},
            {"label": "50", "value": 0, "display": "0"},
            {"label": "MISS", "value": 0, "display": "0"},
        ],
        "pp_targets": [
            {"label": "96% ACC", "value": "1,512"},
            {"label": "98% ACC", "value": "1,903"},
            {"label": "IF FC", "value": "1,858"},
            {"label": "SS PP", "value": "2,012"},
        ],
        "dimension_max": 11,
        "stars": "12.14",
        "bpm": "405",
        "objects": "573",
        "length": "1:18",
        "map_id": 1475722,
        "score": "19,279,990",
        "pp": "1,857",
        "accuracy": "97.44",
        "combo": "881 / 882x",
        "username": "mrekk",
        "user_id": 7562902,
        "country": "AU",
        "global_rank": 1,
        "country_rank": 1,
        "profile_third_value": "Lv.107",
    }

    await warm_up_native_renderer()
    _background_jpeg.cache_clear()
    _atmosphere_rgba.cache_clear()
    cold_started = time.perf_counter()
    await render_score_svg(data)
    cold_elapsed = time.perf_counter() - cold_started
    samples = []
    for _index in range(3):
        started = time.perf_counter()
        await render_score_svg(data)
        samples.append(time.perf_counter() - started)

    # The full first render has a documented local budget of 800 ms.
    assert cold_elapsed < 0.8, cold_elapsed
    # Raster plus final encoding have a combined local budget of 500 ms.
    assert statistics.median(samples) < 0.5, samples
