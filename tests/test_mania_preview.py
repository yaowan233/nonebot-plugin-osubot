from pathlib import Path


STANDARD_CONVERT = """osu file format v14

[General]
Mode: 0

[Metadata]
Title:Convert Test
Artist:OSUBot
Creator:Tester
Version:Preview

[Difficulty]
HPDrainRate:5
CircleSize:4
OverallDifficulty:8
SliderMultiplier:1.4
SliderTickRate:1

[TimingPoints]
0,500,4,2,0,100,1,0

[HitObjects]
32,192,0,1,0,0:0:0:0:
96,192,500,1,0,0:0:0:0:
160,192,1000,1,0,0:0:0:0:
224,192,1500,1,0,0:0:0:0:
288,192,2000,1,0,0:0:0:0:
352,192,2500,1,0,0:0:0:0:
416,192,3000,1,0,0:0:0:0:
480,192,3500,1,0,0:0:0:0:
64,192,4000,2,0,B|128:192,1,280
448,192,5500,8,0,6500
"""


async def test_standard_mania_preview_uses_convert_key_count_and_long_notes(tmp_path: Path):
    from nonebot_plugin_osubot.mania import generate_preview_pic, prepare_mania_preview_map

    osu_file = tmp_path / "convert.osu"
    osu_file.write_text(STANDARD_CONVERT, encoding="utf-8")

    beatmap = prepare_mania_preview_map(osu_file)

    assert beatmap.mode == 3
    assert beatmap.circle_size == 7
    assert len(beatmap.hits) == 8
    assert len(beatmap.holds) == 2
    assert beatmap.stack().column.max() == 6
    assert (await generate_preview_pic(osu_file)).getbuffer().nbytes > 0


def test_animated_preview_converts_requested_mania_mode():
    from nonebot_plugin_osubot.draw.osu_preview import _convert_preview_mode

    converted = _convert_preview_mode(STANDARD_CONVERT, 3)

    assert "Mode: 3" in converted
    assert "CircleSize:7" in converted
    assert ",128," in converted
