from pathlib import Path
from runpy import run_path


HELP_DATA = run_path(Path(__file__).parents[1] / "src" / "nonebot_plugin_osubot" / "help_data.py")
HELP_TOPICS = HELP_DATA["HELP_TOPICS"]
get_command_help = HELP_DATA["get_command_help"]


def test_help_topic_aliases():
    assert get_command_help("BP") == HELP_TOPICS["score"]
    assert get_command_help("/bpa") == HELP_TOPICS["score"]
    assert get_command_help("hs") == HELP_TOPICS["score"]
    assert get_command_help("谱面") == HELP_TOPICS["map"]
    assert get_command_help("vp") == HELP_TOPICS["map"]
    assert get_command_help("/bg") == HELP_TOPICS["map"]
    assert get_command_help("预览") == HELP_TOPICS["map"]
    assert get_command_help("rank") == HELP_TOPICS["profile"]
    assert get_command_help("SB服") == HELP_TOPICS["sb"]


def test_all_help_contains_important_short_commands():
    help_text = get_command_help("all")
    for command in ("/bind", "/mode", "/bl", "/rl", "/pl", "/sc", "/m", "/bm", "/bg", "/vp"):
        assert command in help_text


def test_unknown_help_topic_returns_available_topics():
    assert "可用主题" in get_command_help("not-a-topic")
