from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
import pytest


def test_fit_text_shrinks_long_labels():
    from nonebot_plugin_osubot.draw.svg_render import fit_text

    assert fit_text("short", 500, 54, 30) == 54
    assert fit_text("A very long beatmap title that cannot fit the slot", 300, 54, 30) < 54


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
    assert 'x="521.625" y="226" width="50.625" height="36"' in svg
    assert ">NM</text>" not in svg

    result = await render_score_svg(data)

    with Image.open(result) as image:
        assert image.format == "JPEG"
        assert image.size == (1440, 900)
        # The rank art and white title both occupy the top half. A missing file
        # URI or font regression leaves these sample areas nearly black.
        assert image.crop((1040, 100, 1360, 460)).convert("L").getextrema()[1] > 150
        assert image.crop((400, 95, 750, 160)).convert("L").getextrema()[1] > 150
        rate_region = image.crop((465, 236, 515, 256)).convert("RGB")
        assert any(
            red > 170 and red > green * 1.35
            for y in range(rate_region.height)
            for x in range(rate_region.width)
            for red, green, _blue in (rate_region.getpixel((x, y)),)
        )
