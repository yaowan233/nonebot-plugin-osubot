"""Recover native .osu download failures using the plugin's mirror downloader."""

import sys
import json
import shutil
import asyncio
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from .. import file


async def run_core_worker(request: dict) -> dict:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("core_preview_worker.py")),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await process.communicate(json.dumps(request).encode())
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError(stderr.decode(errors="replace")[-2000:])
    return json.loads(stdout)


async def recover_preview_download(beatmap_id: int | str, options: dict) -> dict:
    # Always fetch anew: unranked maps may have changed since the previous render.
    source = await file.download_osu("native-preview", beatmap_id)
    content = source.read_bytes()
    if not content.lstrip(b"\xef\xbb\xbf\r\n ").startswith(b"osu file format"):
        raise ValueError("下载结果不是有效的 osu 谱面文件")
    key = hashlib.sha256(content + json.dumps(options, sort_keys=True).encode()).hexdigest()
    output_dir = (file.map_path / "native-preview" / "outputs").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{beatmap_id}-{key}.{options['format']}"
    # 0.1.6 initializes config once per process. Isolate the recovery invocation
    # so changing its cache path cannot affect concurrent normal renders.
    with TemporaryDirectory(prefix="osubot-preview-") as temporary:
        root = Path(temporary)
        cache = root / "osu-download-cache"
        cache.mkdir()
        (cache / f"{beatmap_id}.osu").write_bytes(content)
        request = {
            "bid": beatmap_id,
            **options,
            # This is a fresh private cache containing only the newly downloaded map.
            "no_cache": False,
            "config": json.dumps({"paths": {"CACHE_DIR": str(root), "OUTPUT_DIR": str(root / "outputs")}}),
        }
        result = await run_core_worker(request)
        output = result.get("preview-img")
        if not isinstance(output, str) or not output or not Path(output).is_file() or not Path(output).stat().st_size:
            raise ValueError("原生渲染恢复结果缺少有效的 preview-img")
        staging = target.with_name(f".{target.name}.{root.name}.tmp")
        try:
            shutil.copyfile(output, staging)
            staging.replace(target)
        finally:
            staging.unlink(missing_ok=True)
    return {**result, "preview-img": str(target)}
