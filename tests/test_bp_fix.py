import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import nonebot
import pytest
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session


UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"
MATCHER_MODULE = "nonebot_plugin_osubot.matcher.bp_fix"
FAKE_IMAGE = b"BP_FIX_IMAGE"


def _score(pp=100.0, *, misses=1, combo=900, map_combo=1000, objects=1000, rank="A"):
    return SimpleNamespace(
        passed=True,
        pp=pp,
        rank=rank,
        ruleset_id=0,
        accuracy=98.0,
        max_combo=combo,
        mods=[],
        statistics=SimpleNamespace(miss=misses, great=objects - misses, ok=0, meh=0),
        beatmap=SimpleNamespace(
            id=1,
            set_id=2,
            checksum=None,
            title="Map",
            artist="Artist",
            version="Insane",
            max_combo=map_combo,
            count_circles=objects,
            count_sliders=0,
            count_spinners=0,
        ),
    )


def test_bp_fix_candidate_uses_one_percent_choke_rule():
    from nonebot_plugin_osubot.draw.bp_fix import is_fix_candidate

    assert is_fix_candidate(_score(misses=10, objects=1000))
    assert not is_fix_candidate(_score(misses=11, objects=1000))
    assert is_fix_candidate(_score(misses=0, combo=999, map_combo=1000))
    assert not is_fix_candidate(_score(misses=0, combo=1000, map_combo=1000))
    assert not is_fix_candidate(_score(misses=0, rank="X"))


def test_bp_fix_payload_reorders_scores_and_preserves_bonus_pp():
    from nonebot_plugin_osubot.draw.bp_fix import FixedCandidate, build_bp_fix_payload

    info = SimpleNamespace(
        id=1,
        username="player",
        country_code="CN",
        statistics=SimpleNamespace(pp=1000.0),
    )
    scores = [_score(100), _score(90)]

    payload = build_bp_fix_payload(info, scores, [FixedCandidate(index=1, fixed_pp=120, max_combo=1000)], None)

    assert payload["current_pp"] == 1000
    assert payload["gain"] == pytest.approx(29.5)
    assert payload["fixed_pp"] == pytest.approx(1029.5)
    assert payload["entries"][0]["old_rank"] == 2
    assert payload["entries"][0]["new_rank"] == 1
    assert payload["entries"][0]["gain"] == 30


def test_bp_fix_svg_contains_summary_and_entries():
    from nonebot_plugin_osubot.draw.bp_fix_svg import build_bp_fix_svg

    payload = {
        "mode": 0,
        "user": {"id": 1, "name": "player", "country": "CN", "avatar_data": None},
        "current_pp": 1000,
        "fixed_pp": 1029.5,
        "gain": 29.5,
        "candidate_count": 1,
        "entries": [
            {
                "old_rank": 2,
                "new_rank": 1,
                "title": "Map",
                "artist": "Artist",
                "version": "Insane",
                "mods": ["HD"],
                "accuracy": 98,
                "misses": 1,
                "combo": 900,
                "max_combo": 1000,
                "old_pp": 90,
                "fixed_pp": 120,
                "gain": 30,
            }
        ],
    }

    svg, height = build_bp_fix_svg(payload)

    assert height == 467
    assert "OSU! BP FIX档案" in svg
    assert "理论 FULL COMBO" in svg
    assert 'data-role="bp-fix-entry"' in svg
    assert "#2 → #1" in svg
    assert "+29.50" in svg


@pytest.mark.asyncio
async def test_bp_fix_svg_renders_to_jpeg():
    from nonebot_plugin_osubot.draw.bp_fix_svg import render_bp_fix_svg

    payload = {
        "mode": 0,
        "user": {"id": 1, "name": "player", "country": "CN", "avatar_data": None},
        "current_pp": 1000,
        "fixed_pp": 1010,
        "gain": 10,
        "candidate_count": 1,
        "entries": [
            {
                "old_rank": 2,
                "new_rank": 1,
                "title": "Map",
                "artist": "Artist",
                "version": "Insane",
                "mods": [],
                "accuracy": 98,
                "misses": 1,
                "combo": 900,
                "max_combo": 1000,
                "old_pp": 90,
                "fixed_pp": 100,
                "gain": 10,
            }
        ],
    }

    result = await render_bp_fix_svg(payload)

    assert result.getvalue().startswith(b"\xff\xd8")


@pytest.mark.asyncio
async def test_bp_fix_matcher_sends_image(app: App):
    from nonebot_plugin_osubot.matcher.bp_fix import bp_fix

    session = make_mock_session()
    session.scalar.return_value = make_mock_user(osu_id=114514, osu_name="player", osu_mode=0)
    event = fake_group_message_event_v11(message=Message("/fix"))
    expected = Message(
        [
            MessageSegment.reply(event.message_id),
            MessageSegment.image(file=f"base64://{base64.b64encode(FAKE_IMAGE).decode()}"),
        ]
    )

    with patch_session(UTILS_MODULE, session):
        with patch(f"{MATCHER_MODULE}.draw_bp_fix", new=AsyncMock(return_value=BytesIO(FAKE_IMAGE))) as draw:
            async with app.test_matcher(bp_fix) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(event, expected, result={"message_id": 1})
                ctx.should_finished()

    draw.assert_awaited_once_with(114514, True, "osu", "osu")
