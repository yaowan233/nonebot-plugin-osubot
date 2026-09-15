"""Bounded preflight checks before osu-tools decodes or converts a beatmap.

Gameplay thresholds follow rosu-pp 3.1's check_suspicion heuristics:
https://github.com/MaxOhn/rosu-pp/blob/v3.1.0/src/model/beatmap/suspicious.rs
The file/line limits and finite-number checks additionally bound parsing work.
This is a heuristic, not a guarantee that arbitrary calculations finish quickly.
"""

import math
from pathlib import Path


MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024


class SuspiciousBeatmapError(ValueError):
    pass


def suspicion_reason(path: str | Path, mode: int | None = None) -> str | None:
    """Return a rejection reason; check both source and requested ruleset limits."""
    source = Path(path)
    if source.stat().st_size > MAX_FILE_BYTES:
        return "file_size"
    times: list[float] = []
    source_mode = 0
    keys = 5.0
    section = ""
    slider_positions = slider_repeats = 0
    bytes_read = 0
    try:
        with source.open("rb") as stream:
            while raw := stream.readline(MAX_LINE_BYTES + 1):
                bytes_read += len(raw)
                if bytes_read > MAX_FILE_BYTES:
                    return "file_size"
                if len(raw) > MAX_LINE_BYTES:
                    return "line_size"
                line = raw.decode("utf-8-sig").strip()
                if not line or line.startswith("//"):
                    continue
                if line.startswith("["):
                    section = line
                    continue
                if section in {"[General]", "[Difficulty]"}:
                    name, _, value = line.partition(":")
                    if section == "[General]" and name.strip() == "Mode":
                        source_mode = int(value)
                        if source_mode not in range(4):
                            return "mode"
                    elif section == "[Difficulty]" and name.strip() == "CircleSize":
                        keys = float(value)
                        if not math.isfinite(keys) or keys < 0 or keys > 18:
                            return "circle_size"
                elif section == "[HitObjects]":
                    fields = line.split(",")
                    x, y, start = map(float, fields[:3])
                    if not all(math.isfinite(value) for value in (x, y, start)):
                        return "non_finite"
                    kind = int(fields[3])
                    times.append(start)
                    if len(times) > 500_000:
                        return "object_count"
                    if kind & 2:
                        # The file stores span count; rosu's repeats exclude the first span.
                        repeats = max(0, int(fields[6]) - 1)
                        distant = abs(x) > 10_000 or abs(y) > 10_000
                        if repeats > 1000 and distant:
                            return "slider_red_flag"
                        if repeats > 1000:
                            slider_repeats += 1
                        elif distant:
                            slider_positions += 1
                        if slider_repeats > 128:
                            return "slider_repeats"
                        if slider_positions > 128:
                            return "slider_positions"
        times.sort()
        if len(times) > 1 and times[-1] - times[0] > 86_400_000:
            return "length"
        for ruleset in {source_mode, source_mode if mode is None else mode}:
            if ruleset not in range(4):
                return "mode"
            if ruleset == 1 and len(times) > 20_000:
                return "object_count"
            if ruleset == 2:
                continue
            factor = max(1, int(keys) // 2) if ruleset == 3 else (2 if ruleset == 1 else 1)
            for count, window in ((200 * factor, 1000), (500 * factor, 10_000)):
                if any(times[i + count] - times[i] < window for i in range(len(times) - count)):
                    return "density"
    except (ValueError, IndexError, UnicodeError):
        return "malformed"
    return None


def is_suspicious(path: str | Path, mode: int | None = None) -> bool:
    return suspicion_reason(path, mode) is not None


def validate_beatmap(path: str | Path, mode: int | None = None) -> None:
    reason = suspicion_reason(path, mode)
    if reason is not None:
        raise SuspiciousBeatmapError(f"检测到可疑谱面，已停止计算（{reason}）")
