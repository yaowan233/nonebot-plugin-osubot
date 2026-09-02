from io import BytesIO

from PIL import Image
import pytest


def _payload(count: int) -> dict:
    return {
        "me_name": "UID 42",
        "title": "已获得成就",
        "subtitle": f"共 {count} 个成就 · OSU",
        "total": count,
        "start": 1,
        "end": count,
        "achievements": [
            {
                "name": f"Achievement {index}",
                "grouping": "Skill & Dedication",
                "achieved_at": "2026-09-02",
                "icon_data": None,
            }
            for index in range(count)
        ],
    }


def test_achievement_svg_uses_five_columns_and_dynamic_height():
    from nonebot_plugin_osubot.draw.medal_svg import build_achievement_svg

    svg, height = build_achievement_svg(_payload(30))

    assert height == 150 + 22 + 6 * 136 + 5 * 14 + 60
    assert svg.count('data-role="achievement-card"') == 30
    assert "已获得成就" in svg
    assert "Achievement 29" in svg
    assert "OSUBOT ACHIEVEMENTS" in svg


@pytest.mark.asyncio
async def test_achievement_svg_raster_smoke():
    from nonebot_plugin_osubot.draw.medal_svg import render_achievement_svg

    result = await render_achievement_svg(_payload(6))

    with Image.open(BytesIO(result)) as image:
        assert image.size == (1280, 900)
