from pathlib import Path
import json
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def mock_preview_map_status(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_osubot.draw import core_preview

    monkeypatch.setattr(core_preview, "osu_api", AsyncMock(return_value={"status": "ranked"}))


async def test_core_adapter_converts_only_standard_maps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from nonebot_plugin_osubot.draw import core_preview

    output = tmp_path / "preview.gif"
    output.write_bytes(b"GIF89a")
    calls: list[dict[str, object]] = []

    async def render(_beatmap_id: int | str, **kwargs: object) -> dict[str, str]:
        calls.append(kwargs)
        return {"preview-img": str(output)}

    monkeypatch.setattr(core_preview, "generate_preview_async", render)

    assert (
        await core_preview.render_with_core(
            123,
            "gif",
            source_mode=0,
            target_mode=2,
            mods=["HD", "GI", "F"],
        )
        == output
    )
    assert calls[-1]["convert"] == "ctb"
    assert calls[-1]["mods"] == "hd"

    await core_preview.render_with_core(123, "gif", source_mode=2, target_mode=2)
    assert calls[-1]["convert"] is None


async def test_core_adapter_rejects_missing_output(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_osubot.draw import core_preview

    monkeypatch.setattr(core_preview, "generate_preview_async", AsyncMock(return_value={}))

    with pytest.raises(core_preview.CorePreviewError, match="preview-img"):
        await core_preview.render_with_core(123, "png")


@pytest.mark.parametrize("status", ["ranked", "pending"])
async def test_core_download_failure_uses_plugin_download(monkeypatch, tmp_path, status):
    from nonebot_plugin_osubot.draw import core_preview, core_preview_recovery
    from nonebot_plugin_osubot import file

    source = tmp_path / "5493993.osu"
    source.write_text("osu file format v14\n[HitObjects]\n", encoding="utf-8")
    output = tmp_path / "preview.gif"
    output.write_bytes(b"GIF89a")
    download = AsyncMock(return_value=source)
    monkeypatch.setattr(file, "download_osu", download)
    monkeypatch.setattr(file, "map_path", tmp_path)
    monkeypatch.setattr(core_preview, "osu_api", AsyncMock(return_value={"status": status}))
    renderer = AsyncMock(
        side_effect=core_preview.PreviewError(
            "download error: failed to download beatmap 5493993: "
            "https://osu.ppy.sh/osu/5493993: Connection Failed: tls connection init failed: unexpected end of file"
        )
    )

    async def render(kwargs):
        bid = kwargs["bid"]
        config = json.loads(kwargs["config"])
        cached = Path(config["paths"]["CACHE_DIR"]) / "osu-download-cache" / f"{bid}.osu"
        assert cached.read_bytes() == source.read_bytes()
        assert kwargs["no_cache"] is False
        assert kwargs["mods"] == "hr"
        assert kwargs["format"] == "gif"
        return {"preview-img": str(output)}

    worker = AsyncMock(side_effect=render)
    monkeypatch.setattr(core_preview, "generate_preview_async", renderer)
    monkeypatch.setattr(core_preview_recovery, "run_core_worker", worker)
    result = await core_preview.render_with_core(5493993, "gif", mods=["HR"])
    assert result.read_bytes() == output.read_bytes()
    download.assert_awaited_once()
    renderer.assert_awaited_once()
    worker.assert_awaited_once()


async def test_download_recovery_renders_local_map_with_native_library(monkeypatch, tmp_path):
    from nonebot_plugin_osubot.draw.core_preview_recovery import recover_preview_download
    from nonebot_plugin_osubot import file

    source = Path(__file__).parent / "fixtures" / "calculator-mania.osu"
    monkeypatch.setattr(file, "download_osu", AsyncMock(return_value=source))
    monkeypatch.setattr(file, "map_path", tmp_path)
    result = await recover_preview_download(5493993, {"format": "png", "no_cache": True})
    assert Path(result["preview-img"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


async def test_core_does_not_retry_non_download_errors(monkeypatch):
    from nonebot_plugin_osubot.draw import core_preview

    recovery = AsyncMock()
    monkeypatch.setattr(core_preview, "recover_preview_download", recovery)
    monkeypatch.setattr(
        core_preview, "generate_preview_async", AsyncMock(side_effect=core_preview.PreviewError("bad mod"))
    )
    with pytest.raises(core_preview.CorePreviewError, match="bad mod"):
        await core_preview.render_with_core(123, "gif")
    recovery.assert_not_awaited()


async def test_core_download_recovery_failure_is_bounded(monkeypatch):
    from nonebot_plugin_osubot.draw import core_preview

    recovery = AsyncMock(side_effect=RuntimeError("all mirrors failed"))
    renderer = AsyncMock(side_effect=core_preview.PreviewError("failed to download beatmap 123: tls error"))
    monkeypatch.setattr(core_preview, "recover_preview_download", recovery)
    monkeypatch.setattr(core_preview, "generate_preview_async", renderer)
    with pytest.raises(core_preview.CorePreviewError, match="all mirrors failed"):
        await core_preview.render_with_core(123, "gif")
    renderer.assert_awaited_once()
    recovery.assert_awaited_once()


@pytest.mark.parametrize(("mods", "expected"), [(["CL"], None), (["cl", "HD", "DT"], "hd+dt")])
async def test_core_adapter_ignores_classic_mod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mods, expected):
    from nonebot_plugin_osubot.draw import core_preview

    output = tmp_path / "preview.gif"
    output.write_bytes(b"GIF89a")

    async def render(_beatmap_id, **kwargs):
        # Native renderer rejects the Classic marker attached to stable scores.
        if "cl" in (kwargs["mods"] or "").split("+"):
            raise core_preview.PreviewError("unknown or unsupported mod token: 'CL'")
        assert kwargs["mods"] == expected
        return {"preview-img": str(output)}

    monkeypatch.setattr(core_preview, "generate_preview_async", render)
    assert await core_preview.render_with_core(123, "gif", mods=mods) == output


def test_core_adapter_wraps_artifact_read_failures(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_osubot.draw import core_preview

    def fail_open(_path: Path, *_args: object, **_kwargs: object):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "open", fail_open)

    with pytest.raises(core_preview.CorePreviewError, match="读取原生渲染产物失败"):
        core_preview.validate_core_output_readable(Path("preview.mp4"))


async def test_preview_falls_back_when_native_rendering_fails(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_osubot.draw import osu_preview

    native = AsyncMock(side_effect=osu_preview.CorePreviewError("broken"))
    legacy = AsyncMock(return_value=b"legacy-gif")
    monkeypatch.setattr(osu_preview, "_core_bytes", native)
    monkeypatch.setattr(osu_preview, "_legacy_draw_osu_preview", legacy)

    result = await osu_preview.draw_osu_preview(123, 456, source_mode=0, target_mode=2)

    assert result == b"legacy-gif"
    native.assert_awaited_once_with(123, 0, 2, None, fmt="gif")
    legacy.assert_awaited_once_with(123, 456, full=False, target_mode=2)


async def test_full_video_estimate_is_sent_once_when_native_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from nonebot_plugin_osubot.draw import osu_preview

    native = AsyncMock(side_effect=osu_preview.CorePreviewError("broken"))
    video = tmp_path / "preview.mp4"
    video.write_bytes(b"video")

    async def render_legacy(*_args: object, progress_callback, **_kwargs: object) -> Path:
        await progress_callback(120.0)
        return video

    estimate = AsyncMock()
    monkeypatch.setattr(osu_preview, "_core_full_video", native)
    monkeypatch.setattr(osu_preview, "_legacy_draw_full_osu_preview", render_legacy)

    result = await osu_preview.draw_full_osu_preview(
        123,
        456,
        progress_callback=estimate,
        source_mode=0,
        target_mode=2,
    )

    assert result == video
    # 原生渲染立即失败，延迟预估任务被取消；仅旧链路的 120s 预估被发送一次
    estimate.assert_awaited_once_with(120.0)


@pytest.mark.parametrize("status", ["ranked", "approved", "qualified", "loved", "pending", "wip", "graveyard", None])
@pytest.mark.parametrize("fmt", ["png", "gif", "mp4"])
async def test_preview_cache_only_reuses_ranked_maps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status, fmt):
    from nonebot_plugin_osubot.draw import core_preview

    output = tmp_path / f"preview.{fmt}"
    output.write_bytes(b"preview")
    renderer = AsyncMock(return_value={"preview-img": str(output)})
    monkeypatch.setattr(core_preview, "generate_preview_async", renderer)
    monkeypatch.setattr(core_preview, "osu_api", AsyncMock(return_value={"status": status}))

    assert await core_preview.render_with_core(123, fmt) == output
    assert renderer.call_args.kwargs["no_cache"] is (status != "ranked")


async def test_preview_disables_cache_when_status_lookup_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from nonebot_plugin_osubot.draw import core_preview

    output = tmp_path / "preview.png"
    output.write_bytes(b"preview")
    renderer = AsyncMock(return_value={"preview-img": str(output)})
    monkeypatch.setattr(core_preview, "generate_preview_async", renderer)
    monkeypatch.setattr(core_preview, "osu_api", AsyncMock(side_effect=core_preview.NetworkError("offline")))

    assert await core_preview.render_with_core(123, "png") == output
    assert renderer.call_args.kwargs["no_cache"] is True
