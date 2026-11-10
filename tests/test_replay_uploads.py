import gc
import io
import lzma
import struct
import base64
import asyncio
import hashlib
import zipfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from expiringdict import ExpiringDict
from nonebot.adapters.onebot.v11 import Message, MessageSegment, GroupUploadNoticeEvent

from fake import fake_group_message_event_v11, fake_private_message_event_v11


@pytest.fixture
def uploads(monkeypatch):
    from nonebot_plugin_osubot import replay_uploads as module
    from nonebot_plugin_osubot.draw.replay import ReplayPreview

    cache = ExpiringDict(max_len=16, max_age_seconds=600)
    monkeypatch.setattr(module, "_uploads", cache)
    bot = SimpleNamespace(
        self_id="1",
        adapter=SimpleNamespace(get_name=lambda: "OneBot V11"),
        call_api=AsyncMock(return_value={"url": "https://files.example/replay"}),
    )
    event = fake_group_message_event_v11(user_id=2, group_id=3)

    async def render(**kwargs):
        output = kwargs["output_dir"] / "preview.png"
        output.parent.mkdir(exist_ok=True)
        output.write_bytes(b"png")
        return ReplayPreview(output, {"player": "uploaded", "rulesetId": 3}, {})

    renderer = AsyncMock(side_effect=render)
    monkeypatch.setattr(module, "render_replay_with_core", renderer)
    yield SimpleNamespace(module=module, bot=bot, event=event, renderer=renderer, cache=cache)
    cache.clear()


def map_and_replay():
    osu = b"osu file format v14\n[General]\nMode:3\n[Metadata]\nBeatmapID:0\n"
    checksum = hashlib.md5(osu).hexdigest()
    osr = struct.pack("<Bi", 3, 20200101) + b"\x0b\x20" + checksum.encode() + b"\x00"
    return osu, osr, checksum


async def test_direct_osr_uses_online_lookup_when_map_not_uploaded(uploads):
    u = uploads
    _, osr, _ = map_and_replay()
    session = await u.module.store_replay_attachments(u.bot, u.event, [u.module.ReplayAttachment("play.osr", raw=osr)])
    result = await u.module.analyse_replay_upload(u.bot, u.event)

    options = u.renderer.call_args.kwargs
    assert options["osr_file"] == session.replay
    assert options["osu_file"] is None
    assert options["osz_file"] is None
    assert result.path.read_bytes() == b"png"
    assert not {"user", "score_id", "mods", "convert"}.intersection(options)


async def test_sequential_uploads_use_matching_local_map_and_format(uploads):
    u = uploads
    osu, osr, checksum = map_and_replay()
    await u.module.store_replay_attachments(u.bot, u.event, [u.module.ReplayAttachment("map.osu", raw=osu)])
    session = await u.module.store_replay_attachments(
        u.bot,
        u.event,
        [u.module.ReplayAttachment("play.osr", raw=osr)],
        u.module.ReplayUploadOptions("gif", "30", 5),
    )
    await u.module.analyse_replay_upload(u.bot, u.event)

    options = u.renderer.call_args.kwargs
    assert options["osu_file"] == session.maps[checksum]
    assert options["osu_file"].read_bytes() == osu
    assert (options["fmt"], options["times"], options["duration"]) == ("gif", "30", 5)


async def test_archive_is_matched_without_extracting_original_paths(uploads):
    u = uploads
    osu, osr, _ = map_and_replay()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../../outside.osu", osu)
        zip_file.writestr("other.osu", osu + b"different")
    session = await u.module.store_replay_attachments(
        u.bot,
        u.event,
        [
            u.module.ReplayAttachment("play.osr", raw=osr),
            u.module.ReplayAttachment("map.osz", raw=archive.getvalue()),
        ],
    )
    await u.module.analyse_replay_upload(u.bot, u.event)

    options = u.renderer.call_args.kwargs
    assert options["osu_file"].parent == session.root
    assert options["osu_file"].read_bytes() == osu
    assert options["osz_file"] == session.archive


async def test_wrong_map_does_not_fall_back_to_unrelated_online_map(uploads):
    u = uploads
    osu, osr, _ = map_and_replay()
    await u.module.store_replay_attachments(
        u.bot,
        u.event,
        [
            u.module.ReplayAttachment("map.osu", raw=osu + b"different"),
            u.module.ReplayAttachment("play.osr", raw=osr),
        ],
    )
    with pytest.raises(ValueError, match="MD5"):
        await u.module.analyse_replay_upload(u.bot, u.event)
    u.renderer.assert_not_awaited()


@pytest.mark.parametrize(("user", "group", "bot_id"), [(4, 3, "1"), (2, 4, "1"), (2, 3, "5")])
async def test_uploads_are_private_to_sender_conversation_and_bot(uploads, user, group, bot_id):
    u = uploads
    _, osr, _ = map_and_replay()
    await u.module.store_replay_attachments(u.bot, u.event, [u.module.ReplayAttachment("play.osr", raw=osr)])
    other = SimpleNamespace(self_id=bot_id, adapter=u.bot.adapter)
    with pytest.raises(ValueError, match="没有你的"):
        await u.module.analyse_replay_upload(other, fake_group_message_event_v11(user_id=user, group_id=group))
    u.renderer.assert_not_awaited()


@pytest.mark.parametrize(
    ("name", "content"), [("empty.osr", b""), ("bad.osr", b"wrong"), ("bad.osu", b"html"), ("bad.osz", b"zip")]
)
async def test_invalid_upload_is_removed_and_not_rendered(uploads, name, content):
    u = uploads
    with pytest.raises(ValueError, match=".+"):
        await u.module.store_replay_attachments(u.bot, u.event, [u.module.ReplayAttachment(name, raw=content)])
    session = u.module.get_replay_upload(u.bot, u.event)
    assert list(session.root.iterdir()) == []
    u.renderer.assert_not_awaited()


async def test_oversized_raw_and_http_files_are_bounded(uploads, monkeypatch):
    u = uploads
    monkeypatch.setitem(u.module.UPLOAD_LIMITS, ".osr", 16)
    session = u.module.get_replay_upload(u.bot, u.event, create=True)
    with pytest.raises(ValueError, match="限制"):
        await u.module.save_replay_attachment(
            u.bot, u.event, u.module.ReplayAttachment("large.osr", raw=b"x" * 17), session.root
        )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 17))
    ) as client:
        monkeypatch.setattr(u.module.network_manager, "get_client", AsyncMock(return_value=client))
        with pytest.raises(ValueError, match="限制"):
            await u.module.save_replay_attachment(
                u.bot, u.event, u.module.ReplayAttachment("large.osr", url="https://files.example/a"), session.root
            )
    assert list(session.root.iterdir()) == []


async def test_onebot_group_upload_downloads_via_file_api(uploads, monkeypatch):
    u = uploads
    _, osr, _ = map_and_replay()
    event = GroupUploadNoticeEvent(
        time=1,
        self_id=1,
        post_type="notice",
        notice_type="group_upload",
        user_id=2,
        group_id=3,
        file={"name": "play.osr", "id": "file-id", "busid": 102, "size": len(osr)},
    )
    files = await u.module.replay_attachments(u.bot, event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=osr))) as client:
        monkeypatch.setattr(u.module.network_manager, "get_client", AsyncMock(return_value=client))
        session = await u.module.store_replay_attachments(u.bot, event, files)
    u.bot.call_api.assert_awaited_once_with("get_group_file_url", group_id=3, file_id="file-id", busid=102)
    assert session.replay.read_bytes() == osr
    # A later message from the same sender can access notice uploads.
    assert u.module.get_replay_upload(u.bot, u.event) is session


async def test_onebot_private_message_file_without_url(uploads, monkeypatch):
    u = uploads
    _, osr, _ = map_and_replay()
    event = fake_private_message_event_v11(
        user_id=2, message=Message(MessageSegment("file", {"name": "play.osr", "file_id": "id"}))
    )
    files = await u.module.replay_attachments(u.bot, event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=osr))) as client:
        monkeypatch.setattr(u.module.network_manager, "get_client", AsyncMock(return_value=client))
        await u.module.store_replay_attachments(u.bot, event, files)
    u.bot.call_api.assert_awaited_once_with("get_private_file_url", user_id=2, file_id="id")


def test_expired_upload_cleans_temporary_files(uploads):
    u = uploads
    session = u.module.get_replay_upload(u.bot, u.event, create=True)
    root = session.root
    (root / "test.osr").write_bytes(b"test")
    del session
    u.cache.max_age = 0
    u.module.cleanup_replay_uploads()
    gc.collect()
    assert not root.exists()


async def test_file_rule_ignores_unrelated_notices_and_ordinary_resources(uploads):
    from nonebot_plugin_osubot.matcher.replay_upload import accept_replay_attachments

    u = uploads
    notice = SimpleNamespace(get_type=lambda: "notice", notice_type="notify")
    assert not await accept_replay_attachments(u.bot, notice, {})
    resource = fake_group_message_event_v11(
        user_id=2,
        group_id=3,
        message=Message(MessageSegment("file", {"name": "map.osu", "url": "https://files.example/map"})),
    )
    assert not await accept_replay_attachments(u.bot, resource, {})
    u.module.get_replay_upload(u.bot, resource, create=True)
    state = {}
    assert await accept_replay_attachments(u.bot, resource, state)
    assert state["replay_attachments"][0].name == "map.osu"


@pytest.mark.parametrize("command", ["/ra 上传 +png", "/replay 上传 +gif"])
async def test_upload_command_registers_session_and_prompts_for_files(app, uploads, command):
    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter, Bot
    from nonebot_plugin_osubot.matcher.replay import replay_analysis

    event = fake_group_message_event_v11(user_id=2, group_id=3, message=Message(command))
    async with app.test_matcher(replay_analysis) as ctx:
        bot = ctx.create_bot(base=Bot, adapter=nonebot.get_adapter(Adapter))
        ctx.receive_event(bot, event)
        ctx.should_call_send(
            event,
            Message(
                [
                    MessageSegment.reply(event.message_id),
                    MessageSegment.text(
                        "请在 10 分钟内发送 .osr；自制谱面请先发送匹配的 .osu，视频可先发送含音频的 .osz。"
                        "也可直接发送 .osr 开始默认分析。"
                    ),
                ]
            ),
            result={"message_id": 2},
        )
        ctx.should_finished()


@pytest.mark.parametrize("private", [False, True])
async def test_actual_uploaded_file_event_dispatches_analysis(app, uploads, monkeypatch, private):
    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter, Bot
    from nonebot_plugin_osubot.matcher.replay_upload import replay_file_notice, replay_file_message

    u = uploads
    _, osr, _ = map_and_replay()
    if private:
        event = fake_private_message_event_v11(
            user_id=2, message=Message(MessageSegment("file", {"name": "play.osr", "file_id": "file-id"}))
        )
        matcher, api, params = replay_file_message, "get_private_file_url", {"user_id": 2, "file_id": "file-id"}
    else:
        event = GroupUploadNoticeEvent(
            time=1,
            self_id=1,
            post_type="notice",
            notice_type="group_upload",
            user_id=2,
            group_id=3,
            file={"name": "play.osr", "id": "file-id", "size": len(osr), "busid": 102},
        )
        matcher, api, params = (
            replay_file_notice,
            "get_group_file_url",
            {"group_id": 3, "file_id": "file-id", "busid": 102},
        )
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=osr))) as client:
        monkeypatch.setattr(u.module.network_manager, "get_client", AsyncMock(return_value=client))
        async with app.test_matcher(matcher) as ctx:
            bot = ctx.create_bot(base=Bot, adapter=nonebot.get_adapter(Adapter), self_id="1")
            ctx.receive_event(bot, event)
            ctx.should_pass_rule(matcher)
            ctx.should_call_api(api, data=params, result={"url": "https://files.example/play.osr"})
            ctx.should_call_send(event, Message("已收到回放，正在分析，请稍候…"), result={"message_id": 2})
            ctx.should_call_send(
                event,
                Message(
                    [
                        MessageSegment.text("回放分析 · uploaded · Mania\n未知 · — · 准确率 — · 最大连击 0x\n"),
                        MessageSegment.image(file="base64://" + base64.b64encode(b"png").decode()),
                    ]
                ),
                result={"message_id": 3},
            )
    u.renderer.assert_awaited_once()


async def test_uploaded_unpublished_replay_and_map_render_offline(uploads, monkeypatch):
    from nonebot_plugin_osubot.draw.replay import render_replay_with_core

    u = uploads
    monkeypatch.setattr(u.module, "render_replay_with_core", render_replay_with_core)
    osu = (Path(__file__).parent / "fixtures" / "calculator-mania.osu").read_bytes()

    def string(value):
        content = value.encode()
        return b"\x0b" + bytes([len(content)]) + content if content else b"\x00"

    frames = lzma.compress(b"0|0|0|0,1000|0|0|0,-12345|0|0|1,", format=lzma.FORMAT_ALONE)
    osr = (
        struct.pack("<Bi", 3, 20200101)
        + string(hashlib.md5(osu).hexdigest())
        + string("Local player")
        + string("")
        + struct.pack("<6HiHBi", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        + string("")
        + struct.pack("<qi", 0, len(frames))
        + frames
        + struct.pack("<q", 0)
    )
    await u.module.store_replay_attachments(
        u.bot,
        u.event,
        [
            u.module.ReplayAttachment("map.osu", raw=osu),
            u.module.ReplayAttachment("play.osr", raw=osr),
        ],
        u.module.ReplayUploadOptions("png"),
    )
    result = await u.module.analyse_replay_upload(u.bot, u.event)
    assert result.path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.replay_info["player"] == "Local player"
    assert result.replay_info["rulesetId"] == 3


async def test_cancelling_request_keeps_inputs_until_native_render_finishes(uploads):
    u = uploads
    _, osr, _ = map_and_replay()
    await u.module.store_replay_attachments(u.bot, u.event, [u.module.ReplayAttachment("first.osr", raw=osr)])
    started, release = asyncio.Event(), asyncio.Event()
    read_content = []
    original = u.renderer.side_effect

    async def render(**kwargs):
        started.set()
        await release.wait()
        read_content.append(kwargs["osr_file"].read_bytes())
        return await original(**kwargs)

    u.renderer.side_effect = render
    task = asyncio.create_task(u.module.analyse_replay_upload(u.bot, u.event))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    replacement = asyncio.create_task(
        u.module.store_replay_attachments(u.bot, u.event, [u.module.ReplayAttachment("next.osr", raw=osr + b"next")])
    )
    try:
        await asyncio.sleep(0)
        assert not replacement.done()
    finally:
        release.set()
        await asyncio.wait_for(replacement, timeout=1)
    assert read_content == [osr]
