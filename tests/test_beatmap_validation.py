from pathlib import Path

import pytest


def write_map(tmp_path, objects, mode=0, keys=4):
    path = tmp_path / "check.osu"
    path.write_text(
        f"osu file format v14\n[General]\nMode:{mode}\n[Difficulty]\nCircleSize:{keys}\n[HitObjects]\n"
        + "\n".join(objects),
        encoding="utf-8",
    )
    return path


def circle(time):
    return f"64,192,{time},1,0,0:0:0:0:"


def test_normal_mania_is_not_suspicious():
    from nonebot_plugin_osubot.beatmap_validation import is_suspicious

    assert not is_suspicious(Path(__file__).parent / "fixtures" / "calculator-mania.osu")


@pytest.mark.parametrize(("count", "duration", "expected"), [(201, 999, True), (201, 1000, False)])
def test_density_window_boundary(tmp_path, count, duration, expected):
    from nonebot_plugin_osubot.beatmap_validation import is_suspicious

    path = write_map(tmp_path, [circle(i * duration / (count - 1)) for i in range(count)])
    assert is_suspicious(path) is expected


def test_mania_density_accounts_for_keys(tmp_path):
    from nonebot_plugin_osubot.beatmap_validation import is_suspicious

    path = write_map(tmp_path, [circle(i) for i in range(300)], mode=3)
    assert not is_suspicious(path)


def test_length_uses_sorted_times(tmp_path):
    from nonebot_plugin_osubot.beatmap_validation import suspicion_reason

    path = write_map(tmp_path, [circle(86_400_001), circle(0)])
    assert suspicion_reason(path) == "length"


def test_taiko_object_limit_applies_before_conversion(tmp_path):
    from nonebot_plugin_osubot.beatmap_validation import suspicion_reason

    path = write_map(tmp_path, [circle(i * 100) for i in range(20_001)])
    assert suspicion_reason(path) is None
    assert suspicion_reason(path, mode=1) == "object_count"


@pytest.mark.parametrize(
    ("objects", "reason"),
    [
        (["10001,192,0,2,0,L|64:192,1002,100"], "slider_red_flag"),
        (["64,192,0,2,0,L|64:192,1002,100"] * 129, "slider_repeats"),
        (["10001,192,0,2,0,L|64:192,1,100"] * 129, "slider_positions"),
        ([circle("nan")], "non_finite"),
        (["broken"], "malformed"),
    ],
)
def test_bad_data_is_rejected(tmp_path, objects, reason):
    from nonebot_plugin_osubot.beatmap_validation import suspicion_reason

    assert suspicion_reason(write_map(tmp_path, objects)) == reason


@pytest.mark.parametrize("entry", ["calculate", "calculate_many", "stars", "map_attributes"])
def test_all_calculator_entries_reject_before_decoder(tmp_path, monkeypatch, entry):
    from nonebot_plugin_osubot.calculator import CachedOsuCalculator
    from nonebot_plugin_osubot.beatmap_validation import SuspiciousBeatmapError

    calculator = CachedOsuCalculator()
    path = write_map(tmp_path, [circle("nan")])

    def forbidden(*args, **kwargs):
        pytest.fail("Suspicious input reached .NET decoding")

    monkeypatch.setattr(calculator, "_load_working_beatmap", forbidden)
    args = ([{"file_path": str(path), "mode": 0}],) if entry == "calculate_many" else (str(path), 0, [])
    with pytest.raises(SuspiciousBeatmapError, match="non_finite"):
        getattr(calculator, entry)(*args)


def test_validation_is_repeated_after_file_changes(tmp_path):
    from nonebot_plugin_osubot.beatmap_validation import is_suspicious

    path = write_map(tmp_path, [circle(0)])
    assert not is_suspicious(path)
    path.write_text(path.read_text() + "\n" + circle("nan"))
    assert is_suspicious(path)


def test_oversized_line_is_bounded(tmp_path):
    from nonebot_plugin_osubot.beatmap_validation import MAX_LINE_BYTES, suspicion_reason

    path = tmp_path / "large.osu"
    path.write_bytes(b"/" * (MAX_LINE_BYTES + 1))
    assert suspicion_reason(path) == "line_size"
