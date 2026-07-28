from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("acronym", "speed_change", "expected"),
    [
        ("DT", None, None),
        ("DT", 1.5, None),
        ("NC", 1.5, None),
        ("HT", 0.75, None),
        ("DT", 1.2, "1.20×"),
        ("NC", 1.33, "1.33×"),
        ("HT", 0.5, "0.50×"),
        ("HD", 1.2, None),
    ],
)
def test_speed_change_label_hides_defaults(acronym: str, speed_change: float | None, expected: str | None):
    from nonebot_plugin_osubot.mods import get_speed_change_label
    from nonebot_plugin_osubot.schema.score import Mod

    settings = {"speed_change": speed_change} if speed_change is not None else None
    assert get_speed_change_label(Mod(acronym=acronym, settings=settings)) == expected


def test_nc_inherits_custom_dt_speed_label():
    from nonebot_plugin_osubot.mods import get_speed_change_labels
    from nonebot_plugin_osubot.schema.score import Mod

    mods = [Mod(acronym="DT", settings={"speed_change": 1.2}), Mod(acronym="NC")]

    assert get_speed_change_labels(mods)["NC"] == "1.20×"


def test_score_templates_include_speed_change_markers():
    template_root = Path(__file__).parents[1] / "src" / "nonebot_plugin_osubot" / "draw"

    assert "mod.speed_change" in (template_root / "score_templates" / "index.html").read_text(encoding="utf-8")
    assert "x.speed_changes" in (template_root / "bp_templates" / "index.html").read_text(encoding="utf-8")
    assert "play.speed_changes" in (template_root / "score_history_templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "bp-speed-change" in (template_root / "info_templates" / "index.html").read_text(encoding="utf-8")
