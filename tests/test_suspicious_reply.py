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
