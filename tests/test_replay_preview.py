import json
import io
import lzma
import wave
import struct
import hashlib
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from nonebot.adapters.onebot.v11 import Message


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("6086051920", {"score_id": "6086051920"}),
        ("https://osu.ppy.sh/scores/6086051920", {"score_id": "6086051920"}),
        ("peppy 4498112:m +gif", {"user": "peppy", "bid": "4498112", "mode": "mania", "fmt": "gif", "duration": 10}),
        (":c recent +fail +png", {"mode": "fruits", "include_fails": True, "score_select": "recent"}),
        ("user=2 bid=42 +mp4 times=30 duration=5", {"user": "2", "bid": "42", "times": "30", "duration": 5}),
        ("player with spaces 42", {"user": "player with spaces", "bid": "42"}),
        ("", {"user": None, "score_id": None}),
    ],
)
def test_replay_query_sources_and_options(text, expected):
    from nonebot_plugin_osubot.matcher.replay import parse_replay_query

    query = parse_replay_query(text)
    for key, value in expected.items():
        assert getattr(query, key) == value


@pytest.mark.parametrize(
    "text",
    [
        "0",
        "peppy bid=-1",
        "best",
        "peppy 42 +fail",
        "123 :m",
        "123 recent",
        "https://osu.ppy.sh/scores/osu/123",
        "123 user=peppy",
        "peppy :invalid",
        "123 +gif +png",
        "123 times=nan duration=5",
        "123 times=-1 duration=5",
        "123 duration=inf +gif",
        "123 duration=31 +mp4",
        "123 times=1",
        "123 +mp4 times=1+2",
        "123 +gif times=1+2+3+4+5",
        "123 duration=1 duration=2",
    ],
)
def test_replay_query_rejects_invalid_options(text):
    from nonebot_plugin_osubot.matcher.replay import parse_replay_query

    with pytest.raises(ValueError, match=".+"):
        parse_replay_query(text)


async def test_replay_adapter_passes_local_files_without_mod_overrides(monkeypatch, tmp_path):
    from nonebot_plugin_osubot.draw import replay, core_preview_settings

    output = tmp_path / "preview.gif"
    output.write_bytes(b"GIF89a")
    renderer = AsyncMock(return_value={"preview-img": str(output), "replay-info": {"player": "test"}})
    monkeypatch.setattr(replay, "generate_replay_preview_async", renderer)
    monkeypatch.setattr(core_preview_settings, "plugin_config", SimpleNamespace(osu_client=42, osu_key="test-key"))
    result = await replay.render_replay_with_core(osr_file="play.osr", osu_file="map.osu", fmt="gif")

    assert result.path == output
    assert result.replay_info["player"] == "test"
    args, kwargs = renderer.call_args
    assert args == (Path("play.osr").resolve(),)
    assert kwargs["osu_file"] == Path("map.osu").resolve()
    assert not {"mods", "convert", "mode", "score_select", "include_fails"}.intersection(kwargs)
    assert json.loads(kwargs["config"])["download"]["auth"]["OSU_CLIENT_ID"] == "42"


@pytest.mark.parametrize("source", [{"osr_file": "play.osr"}, {"score_id": 123}, {"user": "player", "bid": 42}])
async def test_replay_adapter_uses_installed_renderer_signature(monkeypatch, tmp_path, source):
    import inspect

    from osu_beatmap_preview import generate_replay_preview_async

    from nonebot_plugin_osubot.draw import replay

    output = tmp_path / "preview.png"
    output.write_bytes(b"png")
    signature = inspect.signature(generate_replay_preview_async)

    async def render(*args, **kwargs):
        signature.bind(*args, **kwargs)
        return {"preview-img": str(output)}

    monkeypatch.setattr(replay, "generate_replay_preview_async", render)
    assert (await replay.render_replay_with_core(**source)).path == output


@pytest.mark.parametrize("sources", [{}, {"osr_file": "play.osr", "score_id": 1}])
async def test_replay_adapter_rejects_ambiguous_sources(sources):
    from nonebot_plugin_osubot.draw.replay import render_replay_with_core
    from nonebot_plugin_osubot.draw.core_preview import CorePreviewError

    with pytest.raises(CorePreviewError, match="只能提供一种"):
        await render_replay_with_core(**sources)


async def test_replay_adapter_reports_native_errors_and_missing_output(monkeypatch):
    from nonebot_plugin_osubot.draw import replay

    renderer = AsyncMock(side_effect=replay.PreviewError("no replay available"))
    monkeypatch.setattr(replay, "generate_replay_preview_async", renderer)
    with pytest.raises(replay.CorePreviewError, match="no replay available"):
        await replay.render_replay_with_core(score_id=123)
    renderer.side_effect = None
    renderer.return_value = {}
    with pytest.raises(replay.CorePreviewError, match="preview-img"):
        await replay.render_replay_with_core(score_id=123)


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
@pytest.mark.parametrize("fmt", ["png", "gif", "mp4"])
async def test_native_replay_renders_all_rulesets_offline(tmp_path, mode, fmt):
    from nonebot_plugin_osubot.draw.replay import render_replay_with_core, replay_summary

    osu = (
        f"osu file format v14\n[General]\nMode:{mode}\nAudioFilename:audio.wav\n"
        "[Metadata]\nTitle:Offline test\nArtist:Test\nVersion:Test\nBeatmapID:42\n"
        "[Difficulty]\nCircleSize:4\nOverallDifficulty:5\nHPDrainRate:5\n"
        "ApproachRate:5\nSliderMultiplier:1.4\nSliderTickRate:1\n"
        "[TimingPoints]\n0,500,4,1,0,100,1,0\n"
        "[HitObjects]\n100,100,1000,1,0\n200,100,1500,1,0\n"
    ).encode()
    osu_path = tmp_path / "map.osu"
    osu_path.write_bytes(osu)

    def osu_string(value):
        encoded = value.encode()
        return b"\x0b" + bytes([len(encoded)]) + encoded if encoded else b"\x00"

    frames = (
        "0|0|0|0,1000|1|0|0,1|0|0|0,499|2|0|0,1|0|0|0,999|0|0|0,"
        if mode == 3
        else "0|100|100|0,1000|100|100|1,1|100|100|0,499|200|100|1,1|200|100|0,999|200|100|0,"
    )
    compressed = lzma.compress((frames + "-12345|0|0|1,").encode(), format=lzma.FORMAT_ALONE)
    osr_path = tmp_path / "play.osr"
    osr_path.write_bytes(
        struct.pack("<Bi", mode, 20200101)
        + osu_string(hashlib.md5(osu).hexdigest())
        + osu_string("Offline player")
        + osu_string("")
        + struct.pack("<6HiHBi", 2, 0, 0, 0, 0, 0, 200, 2, 1, 0)
        + osu_string("")
        + struct.pack("<qi", 0, len(compressed))
        + compressed
        + struct.pack("<q", 0)
    )
    options = {}
    if fmt == "mp4":
        audio = io.BytesIO()
        with wave.open(audio, "wb") as wav:
            wav.setparams((2, 2, 8000, 0, "NONE", "not compressed"))
            wav.writeframes(bytes(4 * 8000 * 4))
        archive = tmp_path / "map.osz"
        with zipfile.ZipFile(archive, "w") as osz:
            osz.writestr("map.osu", osu)
            osz.writestr("audio.wav", audio.getvalue())
        options["osz_file"] = archive
    if fmt != "png":
        options.update(times="0", duration=0.2)
    result = await render_replay_with_core(
        osr_file=osr_path, osu_file=osu_path, fmt=fmt, output_dir=tmp_path / "outputs", **options
    )
    content = result.path.read_bytes()
    if fmt == "png":
        assert content.startswith(b"\x89PNG\r\n\x1a\n")
    elif fmt == "gif":
        assert content.startswith(b"GIF8")
    else:
        assert content[4:8] == b"ftyp"
    assert result.replay_info["rulesetId"] == mode
    assert result.replay_info["player"] == "Offline player"
    summary = replay_summary(result)
    assert "Offline player" in summary
    assert "Offline test [Test]" in summary
    assert "准确率" in summary


@pytest.mark.parametrize("fmt", ["png", "mp4"])
async def test_replay_handler_sends_analysis_without_binding(monkeypatch, tmp_path, fmt):
    from nonebot_plugin_osubot.matcher import replay
    from nonebot_plugin_osubot.draw.replay import ReplayPreview

    output = tmp_path / f"preview.{fmt}"
    output.write_bytes(b"preview")
    renderer = AsyncMock(return_value=ReplayPreview(output, {"player": "test"}, {}))
    binding = AsyncMock()
    message = MagicMock()
    message.__iadd__.return_value = message
    message.finish = AsyncMock()
    monkeypatch.setattr(replay, "render_replay_with_core", renderer)
    monkeypatch.setattr(replay, "find_binding", binding)
    monkeypatch.setattr(replay.UniMessage, "text", MagicMock(return_value=message))
    image = MagicMock()
    video = MagicMock()
    monkeypatch.setattr(replay.UniMessage, "image", image)
    monkeypatch.setattr(replay.UniMessage, "video", video)

    await replay._replay(MagicMock(), Message(f"123 +{fmt}"))

    assert renderer.call_args.kwargs["score_id"] == "123"
    binding.assert_not_awaited()
    if fmt == "mp4":
        video.assert_called_once_with(raw=b"preview", name="preview.mp4")
        image.assert_not_called()
    else:
        image.assert_called_once_with(raw=b"preview")
        video.assert_not_called()
    message.finish.assert_awaited_once_with(reply_to=True)


async def test_replay_handler_uses_bound_user_and_mode(monkeypatch, tmp_path):
    from nonebot_plugin_osubot.matcher import replay
    from nonebot_plugin_osubot.draw.replay import ReplayPreview

    output = tmp_path / "preview.png"
    output.write_bytes(b"png")
    renderer = AsyncMock(return_value=ReplayPreview(output, {}, {}))
    monkeypatch.setattr(replay, "render_replay_with_core", renderer)
    monkeypatch.setattr(replay, "find_binding", AsyncMock(return_value=SimpleNamespace(osu_id=2, osu_mode=3)))
    message = MagicMock()
    message.__iadd__.return_value = message
    message.finish = AsyncMock()
    monkeypatch.setattr(replay.UniMessage, "text", MagicMock(return_value=message))
    monkeypatch.setattr(replay.UniMessage, "image", MagicMock())

    await replay._replay(MagicMock(), Message("recent +fail"))

    assert renderer.call_args.kwargs["user"] == "2"
    assert renderer.call_args.kwargs["mode"] == "mania"
    assert renderer.call_args.kwargs["score_select"] == "recent"
    assert renderer.call_args.kwargs["include_fails"] is True


@pytest.mark.parametrize("command", ["/ra", "/replay", "/回放", "/回放分析", "/ra:m recent +fail +png"])
async def test_replay_commands_are_registered_and_dispatched(app, monkeypatch, command):
    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter, Bot, MessageSegment
    from nonebot.matcher import matchers

    from fake import fake_group_message_event_v11
    from nonebot_plugin_osubot.matcher import replay

    plugin = nonebot.get_plugin("nonebot_plugin_osubot")
    assert replay.replay_analysis in plugin.matcher
    assert replay.replay_analysis in matchers[11]
    monkeypatch.setattr(replay, "find_binding", AsyncMock(return_value=None))
    event = fake_group_message_event_v11(message=Message(command))
    async with app.test_matcher() as ctx:
        bot = ctx.create_bot(base=Bot, adapter=nonebot.get_adapter(Adapter))
        ctx.receive_event(bot, event)
        ctx.should_pass_rule(replay.replay_analysis)
        ctx.should_call_send(
            event,
            Message(
                [
                    MessageSegment.reply(event.message_id),
                    MessageSegment.text("请提供成绩 ID、玩家名，或先用 /bind 绑定账号。发送 /oh 回放 查看用法。"),
                ]
            ),
            result={"message_id": 2},
        )
        ctx.should_finished(replay.replay_analysis)
