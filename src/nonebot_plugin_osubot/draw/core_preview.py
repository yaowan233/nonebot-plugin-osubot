"""Rust 二进制 osu-beatmap-preview 的异步封装。

调用本地编译好的 osu-beatmap-preview 可执行文件渲染谱面预览图/视频，
替代原先基于浏览器(gif.js) + ffmpeg 的渲染链路。

二进制 stdout 输出 JSON，产物绝对路径在 "preview-img" 字段。
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from collections.abc import Sequence

logger = logging.getLogger("nonebot_plugin_osubot.core_preview")


class CorePreviewError(Exception):
    """core 渲染失败时抛出，供上层决定是否 fallback。"""


# mode(int/str) -> 二进制的 --convert 取值。0/std 不需要 convert。
_CONVERT_MAP = {
    "0": None,
    "1": "taiko",
    "2": "ctb",
    "3": "mania",
}

# 这些不是 osu 真实 mod，拼 --mods 时必须剔除（GIF 是插件自定义的伪 mod）。
_NON_OSU_MODS = {"GI", "F", "GIF"}


def _mode_to_convert(mode: int | str | None) -> Optional[str]:
    if mode is None:
        return None
    return _CONVERT_MAP.get(str(mode))


def mods_to_cli(mods: Optional[Sequence[str]]) -> Optional[str]:
    """把 state["mods"]（如 ["HD","HR","GI","F"]）转成二进制的 --mods 串（如 "hd+hr"）。

    - 剔除 GIF 伪 mod（可能被切成 "GI","F"，也可能整段 "GIF"）。
    - 全小写，用 "+" 连接。
    - 无有效 mod 时返回 None（不传 --mods）。
    """
    if not mods:
        return None
    cleaned = [m for m in mods if m and m.upper() not in _NON_OSU_MODS]
    if not cleaned:
        return None
    return "+".join(m.lower() for m in cleaned)


async def render_with_core(
    bin_path: Path,
    bid: int | str,
    fmt: str,
    *,
    convert: Optional[str] = None,
    mods: Optional[str] = None,
    time: Optional[str] = None,
    gif_clip: bool = False,
    gif_clip_label: bool = False,
    preview_30s: bool = False,
    gap: Optional[int] = None,
    no_cache: bool = False,
    timeout: float = 120.0,
) -> Path:
    """调用二进制渲染，返回产物文件的绝对 Path。

    Args:
        bin_path: 二进制绝对路径。
        bid: beatmap id。
        fmt: "png" | "gif" | "mp4"。
        convert: "taiko" | "ctb" | "mania" | None(std)。
        mods: 已格式化的 mod 串，如 "hd+hr"。
        time: 形如 "t1+t2"（秒）。仅截取片段时用；全曲 mp4 不要传。
        gif_clip / gif_clip_label / preview_30s / gap / no_cache: 透传同名 flag。
        timeout: 单次渲染超时（秒）。

    Returns:
        产物文件 Path（gif/png/mp4）。

    Raises:
        CorePreviewError: 二进制缺失、超时、非零退出、JSON 解析失败或产物不存在。
    """
    bin_path = Path(bin_path) if bin_path else None
    if bin_path is None or not bin_path.is_file():
        if bin_path is None:
            raise CorePreviewError(
                "未配置 osu_preview_bin_path（OSU_PREVIEW_BIN_PATH），无法使用二进制渲染，已回退旧链路"
            )
        raise CorePreviewError(f"osu-beatmap-preview 二进制不存在: {bin_path}")

    cmd: list[str] = [str(bin_path), "--bid", str(bid), "--fmt", fmt]
    if convert:
        cmd += ["--convert", convert]
    if mods:
        cmd += ["--mods", mods]
    if time:
        cmd += ["--time", time]
    if gif_clip:
        cmd.append("--gif-clip")
    if gif_clip_label:
        cmd.append("--gif-clip-label")
    if preview_30s:
        cmd.append("--preview-30s")
    if gap is not None:
        cmd += ["--gap", str(gap)]
    if no_cache:
        cmd.append("--no-cache")

    logger.debug("core_preview cmd: %s", " ".join(cmd))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except FileNotFoundError as e:
        raise CorePreviewError(f"无法启动二进制: {e}") from e
    except asyncio.TimeoutError as e:
        raise CorePreviewError(f"渲染超时({timeout}s): bid={bid} fmt={fmt}") from e

    if proc.returncode != 0:
        err = (stderr or b"").decode("utf-8", "ignore").strip()
        raise CorePreviewError(f"二进制退出码 {proc.returncode}: {err[-500:]}")

    out = (stdout or b"").decode("utf-8", "ignore").strip()
    if not out:
        raise CorePreviewError("二进制无 stdout 输出")

    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        raise CorePreviewError(f"stdout 非合法 JSON: {out[:200]}") from e

    img = data.get("preview-img")
    if not img:
        raise CorePreviewError(f"JSON 缺少 preview-img 字段: {data}")

    p = Path(img)
    if not p.is_file():
        raise CorePreviewError(f"产物文件不存在: {p}")
    return p
