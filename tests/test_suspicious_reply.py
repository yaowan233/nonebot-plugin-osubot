from importlib import import_module

import pytest
from nonebot.exception import FinishedException

from fake import fake_group_message_event_v11


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["map", "url_match"])
async def test_suspicious_map_replies_instead_of_crashing_or_staying_silent(tmp_path, monkeypatch, entry):
    from nonebot_plugin_alconna import UniMessage
    from nonebot_plugin_osubot.beatmap_validation import validate_beatmap

    module = import_module(f"nonebot_plugin_osubot.matcher.{entry}")
    path = tmp_path / "bad.osu"
    path.write_text("osu file format v14\n[HitObjects]\n64,192,nan,1,0\n")

    async def rejected_draw(*args, **kwargs):
        validate_beatmap(path)

    replies = []

    async def capture_finish(self, **kwargs):
        replies.append(str(self))
        raise FinishedException

    monkeypatch.setattr(module, "draw_map_info", rejected_draw)
    monkeypatch.setattr(UniMessage, "finish", capture_finish)
    event = fake_group_message_event_v11()
    if entry == "map":
        handler = module._map
        args = (event, {"target": "123", "mods": [], "query": "", "mode_explicit": False})
    else:
        handler = module._url
        args = (event, ("456", "123", None))
    with pytest.raises(FinishedException):
        await handler(*args)
    assert len(replies) == 1
    assert "可疑谱面" in replies[0]
    assert "已停止计算" in replies[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entry", "list_mode"),
    [
        ("_pr", False),
        ("_recent", False),
        ("_pr", True),
        ("_recent", True),
        ("_pass_list", True),
        ("_recent_list", True),
    ],
)
async def test_recent_commands_reply_for_suspicious_maps(monkeypatch, entry, list_mode):
    from unittest.mock import AsyncMock
    from nonebot_plugin_alconna import UniMessage
    from nonebot_plugin_osubot.beatmap_validation import SuspiciousBeatmapError

    module = import_module("nonebot_plugin_osubot.matcher.pr")
    error = SuspiciousBeatmapError("检测到可疑谱面，已停止计算（density）")
    monkeypatch.setattr(module, "draw_score", AsyncMock(side_effect=error))
    monkeypatch.setattr(module, "get_user_scores", AsyncMock(return_value=[object()]))

    def reject_score(*args):
        raise error

    monkeypatch.setattr(module, "cal_score_info", reject_score)
    replies = []

    async def capture_finish(self, **kwargs):
        replies.append(str(self))
        raise FinishedException

    monkeypatch.setattr(UniMessage, "finish", capture_finish)
    state = {
        "mode": "3",
        "range": "1-2" if list_mode else "",
        "day": 1,
        "user": 123,
        "is_lazer": True,
        "source": "osu",
        "mods": [],
        "username": "test",
    }
    args = (state,) if entry.endswith("list") else (fake_group_message_event_v11(), state)
    with pytest.raises(FinishedException):
        await getattr(module, entry)(*args)
    assert len(replies) == 1
    assert "可疑谱面" in replies[0]
    assert "已停止计算" in replies[0]
