import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _checksum(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()  # noqa: S324 - osu! API checksum


@pytest.fixture
def file_module(after_nonebot_init):
    return importlib.import_module("nonebot_plugin_osubot.file")


def test_osu_file_matches_checksum(file_module, tmp_path: Path):
    osu_file = tmp_path / "map.osu"
    osu_file.write_bytes(b"current revision")

    assert file_module.osu_file_matches_checksum(osu_file, _checksum(b"current revision"))
    assert not file_module.osu_file_matches_checksum(osu_file, _checksum(b"old revision"))
    assert file_module.osu_file_matches_checksum(osu_file, None)
    assert not file_module.osu_file_matches_checksum(tmp_path / "missing.osu", None)


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
