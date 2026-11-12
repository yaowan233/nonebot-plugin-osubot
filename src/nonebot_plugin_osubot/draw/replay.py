"""Native replay analysis and its user-facing summary."""

from pathlib import Path
from dataclasses import dataclass
from math import isfinite

from osu_beatmap_preview import PreviewError, generate_replay_preview_async

from .core_preview import PreviewFormat, CorePreviewError, _render_semaphore, _plugin_config, core_output_path
from .core_preview_settings import native_render_config


@dataclass(slots=True)
class ReplayPreview:
    path: Path
    replay_info: dict
    beatmap_info: dict


async def render_replay_with_core(
    *,
    osr_file: str | Path | None = None,
    score_id: int | str | None = None,
    user: int | str | None = None,
    bid: int | str | None = None,
    mode: str | None = None,
    score_select: str | None = None,
    include_fails: bool = False,
    osu_file: str | Path | None = None,
    osz_file: str | Path | None = None,
    fmt: PreviewFormat | None = None,
    times: str | None = None,
    duration: float | None = None,
    output_dir: str | Path | None = None,
) -> ReplayPreview:
    """Keep replay ruleset/mods intact, including when using local cached files."""
    if sum(source is not None for source in (osr_file, score_id, user)) != 1:
        raise CorePreviewError("回放文件、成绩 ID、玩家必须且只能提供一种")
    options = {
        "score_id": score_id,
        "user": user,
        "bid": bid,
        "osu_file": Path(osu_file).resolve() if osu_file is not None else None,
        "osz_file": Path(osz_file).resolve() if osz_file is not None else None,
        "format": fmt,
        "times": times,
        "duration_time": duration,
        "output_dir": output_dir,
        "config": native_render_config(),
        "fps": _plugin_config.osu_preview_video_fps if fmt == "mp4" else None,
    }
    if user is not None:
        options.update(mode=mode, score_select=score_select, include_fails=include_fails)
    try:
        async with _render_semaphore:
            result = await generate_replay_preview_async(
                Path(osr_file).resolve() if osr_file is not None else None, **options
            )
        return ReplayPreview(
            core_output_path(result), result.get("replay-info") or {}, result.get("beatmap-info") or {}
        )
    except CorePreviewError:
        raise
    except (PreviewError, OSError, TypeError, ValueError) as error:
        raise CorePreviewError(f"回放分析失败: {error}") from error


def _replay_values(value: object) -> tuple[object | None, object | None]:
    """Split the renderer's calculated/recorded pair, preserving missing values."""
    if isinstance(value, str) and "/" in value:
        calculated, recorded = value.split("/", 1)
        return (calculated.strip() or None, recorded.strip() or None)
    return value, None


def _display_replay_value(value: object, *, suffix: str = "") -> str:
    calculated, recorded = _replay_values(value)
    if calculated not in (None, "", "-"):
        return f"{calculated}{suffix}"
    if recorded not in (None, "", "-"):
        return f"{recorded}{suffix}（回放记录）"
    return "—"


def _display_replay_accuracy(value: object) -> str:
    calculated, recorded = _replay_values(value)
    for number, suffix in ((calculated, ""), (recorded, "（回放记录）")):
        if number is None or isinstance(number, bool):
            continue
        try:
            accuracy = float(number)
        except (TypeError, ValueError):
            continue
        if isfinite(accuracy) and 0 <= accuracy <= 1:
            return f"{accuracy * 100:.2f}%{suffix}"
    return "—"


def replay_summary(preview: ReplayPreview) -> str:
    info = preview.replay_info
    state = info.get("state") or {}
    metadata = preview.beatmap_info.get("meta-data") or {}
    mode = {0: "osu!", 1: "Taiko", 2: "Catch", 3: "Mania"}.get(info.get("rulesetId"), "未知模式")
    lines = [f"回放分析 · {info.get('player') or '未知玩家'} · {mode}"]
    title = metadata.get("title-unicode") or metadata.get("title")
    if title:
        lines.append(f"{title} [{metadata.get('version', '')}]")
    status = {"Completed": "已完成", "Failed": "未通过", "Playing": "播放中"}.get(state.get("status"), "未知")
    accuracy_text = _display_replay_accuracy(state.get("accuracy"))
    rank = _display_replay_value(state.get("rank"))
    combo = _display_replay_value(state.get("max_combo"), suffix="x")
    lines.append(f"{status} · {rank} · 准确率 {accuracy_text} · 最大连击 {combo}")
    statistics = state.get("statistics") or {}
    if statistics:
        pairs = {name: _replay_values(count) for name, count in statistics.items()}
        lines.append("判定（重算）：" + " / ".join(f"{name}: {value[0]}" for name, value in pairs.items()))
        if any(
            recorded not in (None, "", "-") and str(calculated) != str(recorded)
            for calculated, recorded in pairs.values()
        ):
            lines.append(
                "判定（回放记录）："
                + " / ".join(
                    f"{name}: {recorded if recorded not in (None, '', '-') else '—'}"
                    for name, (_, recorded) in pairs.items()
                )
            )
    if info.get("recorded-score") is not None:
        lines.append(f"回放记录分数：{info['recorded-score']:,}")
    if info.get("recorded-result-differences"):
        lines.append("重算结果与回放记录存在差异，图中显示重算结果。")
    return "\n".join(lines)
