from types import SimpleNamespace


def test_game_mods_accept_strings_dicts_and_objects(after_nonebot_init):
    from nonebot_plugin_osubot.schema.match import Game

    assert Game.parse_mods(["HD", {"acronym": "DT"}, SimpleNamespace(acronym="HR")]) == ["HD", "DT", "HR"]
