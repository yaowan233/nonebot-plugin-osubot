from pathlib import Path
from unittest.mock import AsyncMock

import pytest


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
