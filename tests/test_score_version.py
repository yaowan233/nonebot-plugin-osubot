from datetime import datetime
from types import SimpleNamespace
from pathlib import Path

import pytest
import jinja2


@pytest.mark.parametrize(("legacy_score_id", "expected"), [(None, "lazer"), (123456, "stable")])
def test_score_version_uses_legacy_score_id(legacy_score_id: int | None, expected: str):
    from nonebot_plugin_osubot.schema.score import get_score_version

    assert get_score_version(legacy_score_id) == expected


@pytest.mark.parametrize(("legacy_score_id", "expected"), [(None, "lazer"), (123456, "stable")])
def test_score_history_conversion_preserves_score_version(legacy_score_id: int | None, expected: str):
    from nonebot_plugin_osubot.draw.score_history import _to_unified_score
    from nonebot_plugin_osubot.schema.score import NewStatistics

    score = SimpleNamespace(
        mods=[],
        ruleset_id=0,
        rank="A",
        accuracy=0.98,
        total_score=900000,
        legacy_total_score=12345678 if legacy_score_id is not None else 0,
        ended_at="2026-07-28T12:00:00Z",
        max_combo=500,
        statistics=NewStatistics(great=500),
        passed=True,
        pp=250.0,
        legacy_score_id=legacy_score_id,
    )

    assert _to_unified_score(score).score_version == expected


def test_non_official_scores_have_no_client_version():
    from nonebot_plugin_osubot.schema.score import UnifiedScore, NewStatistics

    score = UnifiedScore(
        mods=[],
        ruleset_id=0,
        rank="A",
        accuracy=98.0,
        total_score=12345678,
        ended_at=datetime(2026, 7, 28, 20, 0),
        max_combo=500,
        statistics=NewStatistics(great=500),
        passed=True,
    )

    assert score.score_version is None


def _mania_score(*, score_version: str, accuracy: float, statistics, rank: str = "A", passed: bool = True):
    from nonebot_plugin_osubot.schema.score import UnifiedScore

    return UnifiedScore(
        mods=[],
        ruleset_id=3,
        rank=rank,
        accuracy=accuracy,
        total_score=900000,
        legacy_total_score=900000 if score_version == "stable" else 0,
        ended_at=datetime(2026, 8, 14, 12, 0),
        max_combo=1000,
        statistics=statistics,
        passed=passed,
        score_version=score_version,
    )


def test_stable_mania_uses_legacy_accuracy_in_mixed_score_queries():
    from nonebot_plugin_osubot.draw.score import cal_score_info
    from nonebot_plugin_osubot.schema.score import NewStatistics

    statistics = NewStatistics(perfect=1, great=1, good=1, ok=1, meh=1, miss=1)
    score = _mania_score(score_version="stable", accuracy=0, statistics=statistics)

    cal_score_info(True, score)

    assert score.accuracy == pytest.approx(52.7777777778)


def test_stable_mania_repairs_incorrect_zero_accuracy_and_f_rank_from_api():
    from nonebot_plugin_osubot.draw.score import cal_score_info
    from nonebot_plugin_osubot.schema.score import NewStatistics

    score = _mania_score(
        score_version="stable",
        accuracy=0,
        statistics=NewStatistics(perfect=800, great=150, good=30, ok=10, meh=5, miss=5),
        rank="F",
        passed=True,
    )

    cal_score_info(True, score)

    assert score.accuracy == pytest.approx(97.4166666667)
    assert score.rank == "S"


def test_lazer_mania_accuracy_is_not_replaced_by_legacy_formula():
    from nonebot_plugin_osubot.draw.score import cal_score_info
    from nonebot_plugin_osubot.schema.score import NewStatistics

    score = _mania_score(
        score_version="lazer",
        accuracy=96.875,
        statistics=NewStatistics(perfect=1, great=1),
    )

    cal_score_info(False, score)

    assert score.accuracy == 96.875


def test_score_version_templates_render_source_badges():
    template_root = Path(__file__).parents[1] / "src" / "nonebot_plugin_osubot" / "draw"

    score_template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(template_root / "score_templates")
    ).get_template("index.html")
    assert 'class="score-version lazer"' in score_template.render(d={"score_version": "lazer"})

    history_template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(template_root / "score_history_templates")
    ).get_template("index.html")
    rendered_history = history_template.render(
        d={
            "user": {"avatar": "", "name": "test", "country": "CN", "global_rank": None, "pp": 0, "id": 1},
            "map": {
                "cover": "",
                "title": "map",
                "artist": "artist",
                "version": "diff",
                "star_color": "#fff",
                "star_text": "#000",
                "stars": 1,
                "bpm": 120,
                "creator": "mapper",
                "id": 1,
            },
            "source": "osu!",
            "score_version": "Lazer + Stable",
            "plays": [
                {
                    "best": False,
                    "passed": True,
                    "index": 1,
                    "rank": "A",
                    "score": 1,
                    "pp": 1,
                    "accuracy": 100,
                    "combo": 1,
                    "judgements": [],
                    "mods": [],
                    "star_color": "#fff",
                    "star_text": "#000",
                    "stars": 1,
                    "date": "2026.01.01 00:00",
                    "score_version": "stable",
                }
            ],
            "disclaimer": "",
            "generated_at": "",
        }
    )
    assert 'class="score-origin stable">Stable</small>' in rendered_history

    bp_template = (template_root / "bp_templates" / "index.html").read_text(encoding="utf-8")
    assert "x.score_version" in bp_template
    assert "score-origin ${x.score_version}" in bp_template
    assert "clientName(x.score_version)" in bp_template
