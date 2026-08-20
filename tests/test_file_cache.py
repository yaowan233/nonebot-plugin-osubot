import hashlib
import importlib
import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image


def _checksum(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()  # noqa: S324 - osu! API checksum


@pytest.fixture
def file_module(after_nonebot_init):
    return importlib.import_module("nonebot_plugin_osubot.file")


class RecordingSemaphore:
    def __init__(self):
        self.entries = 0

    async def __aenter__(self):
        self.entries += 1

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_osu_file_matches_checksum(file_module, tmp_path: Path):
    osu_file = tmp_path / "map.osu"
    osu_file.write_bytes(b"current revision")

    assert file_module.osu_file_matches_checksum(osu_file, _checksum(b"current revision"))
    assert not file_module.osu_file_matches_checksum(osu_file, _checksum(b"old revision"))
    assert file_module.osu_file_matches_checksum(osu_file, None)
    assert not file_module.osu_file_matches_checksum(tmp_path / "missing.osu", None)


def test_badge_cache_path_is_stable(file_module, tmp_path: Path):
    badge = SimpleNamespace(image_url="https://example.com/badge.png", description="Tournament Winner")

    with patch.object(file_module, "badge_cache_path", tmp_path):
        first = file_module.badge_cache_file(badge)
        second = file_module.badge_cache_file(badge)

    assert first == second
    assert first.parent == tmp_path
    assert first.suffix == ".png"
    assert "Tournament" not in first.name


@pytest.mark.asyncio
async def test_image_downloads_use_shared_semaphore(file_module, tmp_path: Path):
    semaphore = RecordingSemaphore()
    response = SimpleNamespace(content=b"image", status_code=200)

    with (
        patch.object(file_module, "image_download_semaphore", semaphore),
        patch.object(file_module, "safe_async_get", new=AsyncMock(return_value=response)),
    ):
        image = await file_module.get_pfm_img("https://example.com/image.png", tmp_path / "image.png")

    assert semaphore.entries == 1
    assert image.getvalue() == b"image"


@pytest.mark.asyncio
async def test_ensure_osu_file_reuses_matching_cache(file_module, tmp_path: Path):
    osu_file = tmp_path / "123" / "456.osu"
    osu_file.parent.mkdir()
    osu_file.write_bytes(b"current revision")
    download = AsyncMock()

    with patch.object(file_module, "map_path", tmp_path), patch.object(file_module, "download_osu", download):
        result = await file_module.ensure_osu_file(123, 456, _checksum(b"current revision"))

    assert result == osu_file
    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_osu_file_refreshes_stale_cache(file_module, tmp_path: Path):
    osu_file = tmp_path / "123" / "456.osu"
    osu_file.parent.mkdir()
    osu_file.write_bytes(b"old revision")

    async def fake_download(set_id: int, map_id: int, checksum: str | None = None) -> Path:
        assert (set_id, map_id, checksum) == (123, 456, _checksum(b"current revision"))
        osu_file.write_bytes(b"current revision")
        return osu_file

    with (
        patch.object(file_module, "map_path", tmp_path),
        patch.object(
            file_module,
            "download_osu",
            side_effect=fake_download,
        ),
    ):
        result = await file_module.ensure_osu_file(123, 456, _checksum(b"current revision"))

    assert result == osu_file
    assert osu_file.read_bytes() == b"current revision"


@pytest.mark.asyncio
async def test_download_osu_retries_official_when_mirror_is_stale(file_module, tmp_path: Path):
    current = b"current revision"
    mirror_response = SimpleNamespace(content=b"old revision")
    official_response = SimpleNamespace(content=current, status_code=200)

    with (
        patch.object(file_module, "map_path", tmp_path),
        patch.object(file_module, "get_first_response", new=AsyncMock(return_value=mirror_response)),
        patch.object(file_module, "safe_async_get", new=AsyncMock(return_value=official_response)),
    ):
        result = await file_module.download_osu.__wrapped__(123, 456, _checksum(current))

    assert result == tmp_path / "123" / "456.osu"
    assert result.read_bytes() == current
    assert list(result.parent.glob("*.tmp")) == []


@pytest.mark.asyncio
async def test_download_osu_rejects_wrong_official_revision(file_module, tmp_path: Path):
    response = SimpleNamespace(content=b"old revision", status_code=200)

    with (
        patch.object(file_module, "map_path", tmp_path),
        patch.object(file_module, "get_first_response", new=AsyncMock(return_value=response)),
        patch.object(file_module, "safe_async_get", new=AsyncMock(return_value=response)),
        pytest.raises(file_module.NetworkError, match="checksum"),
    ):
        await file_module.download_osu.__wrapped__(123, 456, _checksum(b"current revision"))

    assert not (tmp_path / "123" / "456.osu").exists()


def _jpeg_bytes(colour: str) -> BytesIO:
    output = BytesIO()
    Image.new("RGB", (8, 8), colour).save(output, "JPEG")
    output.seek(0)
    return output


@pytest.mark.asyncio
async def test_background_cache_refreshes_only_after_beatmap_revision(after_nonebot_init, tmp_path: Path):
    bg_module = importlib.import_module("nonebot_plugin_osubot.info.bg")
    set_path = tmp_path / "123"
    set_path.mkdir()
    osu_file = set_path / "456.osu"
    cover_file = set_path / "cover.jpg"
    osu_file.write_text("osu file", encoding="utf-8")
    cover_file.write_bytes(_jpeg_bytes("red").getvalue())
    os.utime(osu_file, ns=(1_000_000_000, 1_000_000_000))
    os.utime(cover_file, ns=(2_000_000_000, 2_000_000_000))
    download = AsyncMock(return_value=_jpeg_bytes("blue"))

    with (
        patch.object(bg_module, "map_path", tmp_path),
        patch.object(bg_module, "re_map", return_value="cover.jpg"),
        patch.object(bg_module, "get_map_bg", download),
    ):
        cached = await bg_module.get_bg(456, 123)
        download.assert_not_awaited()
        assert cached.getpixel((0, 0))[0] > cached.getpixel((0, 0))[2]
        cached.close()

        os.utime(osu_file, ns=(3_000_000_000, 3_000_000_000))
        refreshed = await bg_module.get_bg(456, 123)

    download.assert_awaited_once()
    assert refreshed.getpixel((0, 0))[2] > refreshed.getpixel((0, 0))[0]
    refreshed.close()
