from datetime import datetime, timedelta
from types import SimpleNamespace


def make_score(**overrides):
    values = {
        "pp": 321.5,
        "accuracy": 98.75,
        "total_score": 1_234_567,
        "max_combo": 876,
        "rank": "S",
        "score_version": "lazer",
        "ended_at": datetime.now() - timedelta(days=2),
        "mods": [SimpleNamespace(acronym="HD"), SimpleNamespace(acronym="HR")],
        "statistics": SimpleNamespace(miss=0, great=1000),
        "beatmap": SimpleNamespace(
            id=123,
            set_id=456,
            title="Freedom Dive",
            artist="xi",
            version="FOUR DIMENSIONS",
            creator="Nakagawa-Kanon",
            total_length=222,
            bpm=222.22,
            cs=4,
            od=9.5,
            ar=9.8,
            hp=6.5,
            stars=7.25,
        ),
        "beatmapset": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_numeric_aliases_ranges_and_zero_values():
    from nonebot_plugin_osubot.draw.utils import matches_condition_with_regex

    score = make_score()

    assert matches_condition_with_regex(score, "star", "=", "7..8")
    assert matches_condition_with_regex(score, "星数", ">=", "7")
    assert matches_condition_with_regex(score, "hp", "=", "6.5")
    assert matches_condition_with_regex(score, "acc", ">=", "98%")
    assert matches_condition_with_regex(score, "失误", "=", "0")
    assert matches_condition_with_regex(score, "mapid", "=", "123")


def test_text_keyword_client_date_and_fc_filters():
    from nonebot_plugin_osubot.draw.utils import matches_condition_with_regex

    score = make_score()

    assert matches_condition_with_regex(score, "关键词", "=", "freedom")
    assert matches_condition_with_regex(score, "谱师", "~", "kanon$")
    assert matches_condition_with_regex(score, "客户端", "=", "lazer")
    assert matches_condition_with_regex(score, "日期", ">=", (datetime.now() - timedelta(days=3)).date().isoformat())
    assert matches_condition_with_regex(score, "天数", "<=", "3")
    assert matches_condition_with_regex(score, "fc", "=", "是")


def test_mod_filters_support_exact_contains_excludes_and_nomod():
    from nonebot_plugin_osubot.draw.utils import matches_condition_with_regex

    score = make_score()
    nomod = make_score(mods=[SimpleNamespace(acronym="CL")])
    nightcore = make_score(mods=[SimpleNamespace(acronym="NC"), SimpleNamespace(acronym="DT")])

    assert matches_condition_with_regex(score, "mods", "=", "HDHR")
    assert matches_condition_with_regex(score, "mods", "~=", "HD")
    assert matches_condition_with_regex(score, "mods", "!=", "DT")
    assert matches_condition_with_regex(nomod, "mods", "=", "NM")
    assert matches_condition_with_regex(nightcore, "mods", "=", "NC")


def test_multiple_conditions_are_combined_with_and():
    from nonebot_plugin_osubot.draw.utils import filter_scores_with_regex

    matching = make_score()
    low_pp = make_score(pp=100)

    selected = filter_scores_with_regex(
        [matching, low_pp],
        [("pp", ">=", "300"), ("title", "~", "freedom"), ("mods", "!=", "DT")],
    )

    assert selected == [matching]


def test_compact_filters_are_extracted_without_consuming_username():
    from nonebot_plugin_osubot.matcher.utils import extract_bp_shorthands

    conditions = []
    remaining = extract_bp_shorthands("peppy 300pp+ 98a+ 5-7* 7d fc -DT =HDHR", conditions)

    assert remaining.split() == ["peppy"]
    assert conditions == [
        ("stars", "=", "5..7"),
        ("pp", ">=", "300"),
        ("accuracy", ">=", "98"),
        ("days", "<=", "7"),
        ("fc", "=", "true"),
        ("mods", "!=", "DT"),
        ("mods", "=", "HDHR"),
    ]


def test_agent_filter_text_uses_the_same_parser_as_commands():
    from nonebot_plugin_osubot.matcher.utils import parse_bp_filter_text

    conditions, remaining = parse_bp_filter_text('300pp+ 98a+ t~"Freedom Dive" mp~kanon -DT')

    assert remaining == ""
    assert conditions == [
        ("pp", ">=", "300"),
        ("accuracy", ">=", "98"),
        ("mods", "!=", "DT"),
        ("t", "~", "Freedom Dive"),
        ("mp", "~", "kanon"),
    ]


def test_agent_filter_text_reports_unparsed_content():
    from nonebot_plugin_osubot.matcher.utils import parse_bp_filter_text

    conditions, remaining = parse_bp_filter_text("p>=300 这段看不懂")

    assert conditions == [("p", ">=", "300")]
    assert remaining == "这段看不懂"


def test_short_aliases_units_dates_and_custom_speed():
    from nonebot_plugin_osubot.draw.utils import matches_condition_with_regex

    score = make_score(mods=[SimpleNamespace(acronym="DT", settings={"speed_change": 1.2})])

    assert matches_condition_with_regex(score, "p", ">", "300")
    assert matches_condition_with_regex(score, "len", "=", "3m..4m")
    assert matches_condition_with_regex(score, "c", ">", "800x")
    assert matches_condition_with_regex(score, "cl", "=", "l")
    assert matches_condition_with_regex(score, "after", "=", (datetime.now() - timedelta(days=3)).date().isoformat())
    assert matches_condition_with_regex(score, "speed", "=", "1.2")
