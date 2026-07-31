import os
import re
import shutil
import asyncio
from io import BytesIO
from pathlib import Path
from typing import Optional
from zipfile import ZipFile
from dataclasses import dataclass

import numpy as np
from PIL import ImageDraw
from vsrg_tools.osu.OsuHit import OsuHit
from vsrg_tools.osu.OsuHold import OsuHold
from vsrg_tools.osu.OsuMap import OsuMap
from vsrg_tools.osu.lists.notes.OsuHitList import OsuHitList
from vsrg_tools.osu.lists.notes.OsuHoldList import OsuHoldList
from vsrg_tools.algorithms.generate import full_ln
from vsrg_tools.algorithms.playField import PlayField
from vsrg_tools.algorithms.pattern.Pattern import Pattern
from vsrg_tools.algorithms.pattern.combos.PtnCombo import PtnCombo
from vsrg_tools.algorithms.playField.parts import (
    PFDrawSv,
    PFDrawBpm,
    PFDrawLines,
    PFDrawOffsets,
    PFDrawBeatLines,
    PFDrawColumnLines,
)

from ..file import download_map
from ..schema.beatmapsets import BeatmapSets

osu_path = Path() / "data" / "osu"
if not osu_path.exists():
    osu_path.mkdir(parents=True, exist_ok=True)

PREVIEW_BACKGROUND = "#0a1017"
PREVIEW_LANE = "#0e1720"
PREVIEW_LANE_ALT = "#111c26"
PREVIEW_LINE = "#283744"
PREVIEW_STRONG_LINE = "#71818d"
PREVIEW_MUTED = "#677783"
PREVIEW_NOTE = "#dce4e9"
PREVIEW_NOTE_ALT = "#579bb4"
PREVIEW_NOTE_CENTER = "#c2aa69"


@dataclass
class Options:
    rate: Optional[float]
    end_rate: Optional[float]
    od: Optional[float]
    set: Optional[int]
    map: Optional[int] = None
    beatmapsets: Optional[BeatmapSets] = None
    nsv: bool = False
    nln: bool = False
    fln: bool = False
    step: float = 0.05
    gap: float = 150
    thres: float = 100


def _section_lines(osu_file: str, section: str) -> list[str]:
    match = re.search(
        rf"(?ms)^\[{re.escape(section)}\]\s*$\n(.*?)(?=^\[|\Z)",
        osu_file.replace("\r\n", "\n").replace("\r", "\n"),
    )
    if match is None:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.strip() and not line.startswith("//")]


def _difficulty_value(osu_file: str, name: str, default: float) -> float:
    match = re.search(rf"(?m)^{re.escape(name)}\s*:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$", osu_file)
    return float(match.group(1)) if match else default


def _mania_convert_key_count(osu_file: str, hit_object_lines: list[str]) -> int:
    """Match osu!'s stable-compatible key-count selection for std converts."""
    circle_size = round(_difficulty_value(osu_file, "CircleSize", 5))
    overall_difficulty = round(_difficulty_value(osu_file, "OverallDifficulty", 5))
    object_types = []
    for line in hit_object_lines:
        fields = line.split(",")
        if len(fields) < 5:
            continue
        try:
            object_types.append(int(fields[3]))
        except ValueError:
            continue

    if object_types:
        special_count = sum(bool(object_type & (2 | 8)) for object_type in object_types)
        special_ratio = special_count / len(object_types)
        if special_ratio < 0.2:
            return 7
        if special_ratio < 0.3 or circle_size >= 5:
            return 7 if overall_difficulty > 5 else 6
        if special_ratio > 0.6:
            return 5 if overall_difficulty > 4 else 4
    return max(4, min(overall_difficulty + 1, 7))


def _slider_duration(
    start_time: float,
    repeats: int,
    pixel_length: float,
    timing_points: list[tuple[float, float, bool]],
    slider_multiplier: float,
) -> float:
    beat_length = 500.0
    velocity_multiplier = 1.0
    for offset, value, uninherited in timing_points:
        if offset > start_time:
            break
        if uninherited:
            beat_length = value
            velocity_multiplier = 1.0
        elif value < 0:
            velocity_multiplier = max(0.1, min(10.0, -100.0 / value))
    scoring_distance = max(slider_multiplier, 0.1) * 100 * velocity_multiplier
    return max(0.0, pixel_length / scoring_distance * beat_length * max(repeats, 1))


def convert_standard_to_mania_preview(osu_file: str) -> OsuMap:
    """Build a deterministic Mania preview map from an osu!standard file."""
    normalized = osu_file.replace("\r\n", "\n").replace("\r", "\n")
    beatmap = OsuMap.read(normalized.splitlines())
    hit_object_lines = _section_lines(normalized, "HitObjects")
    key_count = _mania_convert_key_count(normalized, hit_object_lines)
    slider_multiplier = _difficulty_value(normalized, "SliderMultiplier", 1.4)

    timing_points: list[tuple[float, float, bool]] = []
    for line in _section_lines(normalized, "TimingPoints"):
        fields = line.split(",")
        if len(fields) < 2:
            continue
        try:
            timing_points.append(
                (
                    float(fields[0]),
                    float(fields[1]),
                    len(fields) < 7 or fields[6].strip() == "1",
                )
            )
        except ValueError:
            continue
    timing_points.sort(key=lambda point: point[0])

    hits: list[OsuHit] = []
    holds: list[OsuHold] = []
    occupied: dict[int, set[int]] = {}
    for index, line in enumerate(hit_object_lines):
        fields = line.split(",")
        if len(fields) < 5:
            continue
        try:
            x = float(fields[0])
            start_time = float(fields[2])
            object_type = int(fields[3])
        except ValueError:
            continue

        timestamp = round(start_time)
        preferred_column = max(0, min(key_count - 1, int(x * key_count / 512)))
        used_columns = occupied.setdefault(timestamp, set())
        column = next(
            (
                (preferred_column + offset) % key_count
                for offset in range(key_count)
                if (preferred_column + offset) % key_count not in used_columns
            ),
            (preferred_column + index) % key_count,
        )
        used_columns.add(column)

        duration = 0.0
        if object_type & 2 and len(fields) >= 8:
            try:
                duration = _slider_duration(
                    start_time,
                    int(fields[6]),
                    float(fields[7]),
                    timing_points,
                    slider_multiplier,
                )
            except ValueError:
                duration = 0.0
        elif object_type & 8 and len(fields) >= 6:
            try:
                duration = max(0.0, float(fields[5]) - start_time)
            except ValueError:
                duration = 0.0

        if duration >= 100:
            holds.append(OsuHold(start_time, column, duration))
        else:
            hits.append(OsuHit(start_time, column))

    if not hits and not holds:
        raise ValueError("谱面没有可用于 Mania 转谱预览的物件")

    # PlayField infers the lane count from the largest used column.
    last_object = holds[-1] if holds else hits[-1]
    last_object.column = key_count - 1
    beatmap.mode = 3
    beatmap.circle_size = key_count
    beatmap.hits = OsuHitList(hits)
    beatmap.holds = OsuHoldList(holds)
    return beatmap


def prepare_mania_preview_map(file: Path) -> OsuMap:
    osu_file = file.read_text(encoding="utf-8-sig")
    mode_match = re.search(r"(?m)^Mode\s*:\s*(\d+)\s*$", osu_file)
    if mode_match is None or int(mode_match.group(1)) == 0:
        return convert_standard_to_mania_preview(osu_file)
    return OsuMap.read(osu_file.replace("\r\n", "\n").replace("\r", "\n").splitlines())


def _preview_note_color(column: int, keys: int) -> str:
    if keys % 2 and column == keys // 2:
        return PREVIEW_NOTE_CENTER
    return PREVIEW_NOTE if column % 2 == 0 else PREVIEW_NOTE_ALT


def _draw_preview_note(
    draw: ImageDraw.ImageDraw,
    field: PlayField,
    column: int,
    offset: float,
    color: str,
) -> None:
    x, y = field.get_pos(offset, column, y_offset=-field.hit_height)
    draw.rectangle(
        (x, y, x + field.note_width - 1, y + field.hit_height - 1),
        fill=color,
    )


def _draw_preview_notes(field: PlayField) -> None:
    draw = ImageDraw.Draw(field.canvas)

    for hold in field.m.holds:
        column = int(hold.column)
        color = _preview_note_color(column, field.keys)
        x = field.get_pos(hold.offset, column)[0]
        head_y = field.get_pos(hold.offset, column, y_offset=-field.hit_height)[1]
        tail_y = field.get_pos(hold.tail_offset, column, y_offset=-field.hit_height)[1]
        top = min(head_y, tail_y) + field.hit_height // 2
        bottom = max(head_y, tail_y) + field.hit_height // 2
        inset = 1
        draw.rectangle(
            (x + inset, top, x + field.note_width - inset - 1, bottom),
            fill=color,
        )

    for hold in field.m.holds:
        column = int(hold.column)
        color = _preview_note_color(column, field.keys)
        for offset in (hold.offset, hold.tail_offset):
            _draw_preview_note(draw, field, column, offset, color)

    for hit in field.m.hits:
        column = int(hit.column)
        color = _preview_note_color(column, field.keys)
        _draw_preview_note(draw, field, column, hit.offset, color)


async def generate_preview_pic(file: Path, full=False) -> BytesIO:
    m = prepare_mania_preview_map(file)
    keys = m.stack().column.max() + 1
    ptn = Pattern.from_note_lists([m.hits, m.holds], include_tails=False)
    grp = ptn.group()
    pf = PlayField(
        m,
        duration_per_px=5,
        note_width=11,
        hit_height=4,
        hold_height=4,
        column_line_width=1,
        padding=54,
        background_color=PREVIEW_BACKGROUND,
    )
    draw = ImageDraw.Draw(pf.canvas)
    lane_step = pf.note_width + pf.column_line_width
    for column in range(pf.keys):
        left = column * lane_step
        draw.rectangle(
            (left, 0, left + pf.note_width - 1, pf.canvas_h),
            fill=PREVIEW_LANE if column % 2 == 0 else PREVIEW_LANE_ALT,
        )

    pf += PFDrawColumnLines(color=PREVIEW_LINE)
    pf += PFDrawBeatLines(
        divisions=(1, 2, 4),
        division_colors={1: PREVIEW_STRONG_LINE, 2: "#34434f", 4: "#1c2832"},
    )
    pf += PFDrawBpm(color="#e65d69", x_offset=28, decimal_places=1)
    pf += PFDrawSv(color="#789f8f", decimal_places=2)
    pf += PFDrawOffsets(interval=4000, decimal_places=0, color=PREVIEW_MUTED)
    _draw_preview_notes(pf)
    if full:
        pf += PFDrawLines.from_combo(
            **PFDrawLines.Colors.RED,
            keys=keys,
            combo=np.concatenate(
                PtnCombo(grp).template_chord_stream(primary=3, secondary=2, keys=keys, and_lower=True),
                axis=0,
            ),
        )
        pf += PFDrawLines.from_combo(
            **PFDrawLines.Colors.PURPLE,
            keys=keys,
            combo=np.concatenate(PtnCombo(grp).template_jacks(minimum_length=2, keys=keys), axis=0),
        )
    byt = BytesIO()
    pf.export_fold(
        max_height=3000,
        stage_line_width=5,
        stage_line_color="#202d37",
    ).save(byt, "png")
    return byt


async def convert_mania_map(options: Options) -> Optional[Path]:
    path = osu_path / f"{options.set}"
    osz_file = await download_map(options.set)
    if not osz_file:
        return
    with ZipFile(osz_file.absolute()) as my_zip:
        my_zip.extractall(path)
    os.remove(osz_file)
    if options.beatmapsets:
        for file in path.rglob("*.osu"):
            osu = OsuMap.read_file(str(file.absolute()))
            if osu.beatmap_id == options.map:
                audio_file_name = osu.audio_file_name
                audio_name = osu.audio_file_name[:-4]
                audio_type = osu.audio_file_name[-4:]
                break
    if options.rate:
        if options.rate > 10:
            options.rate = 10
        end = options.end_rate if options.end_rate else options.rate + 0.01
        if end > 10:
            end = 10.1
        if options.step and abs(options.step) < 0.05:
            options.step = 0.05 if options.step > 0 else -0.05
        if not options.step:
            options.step = 0.05
        tasks = []
        for rate in np.arange(options.rate, end, options.step):
            new_audio_path = path / (audio_name + f"x{rate:.2f}" + audio_type)
            tasks.append(
                asyncio.create_subprocess_shell(
                    f'ffmpeg -i "{(path / audio_file_name).absolute()}" -filter:a "atempo={rate}" -b:a 128k -vn -y '
                    f'"{new_audio_path.absolute()}" -loglevel quiet'
                )
            )
        await asyncio.gather(*tasks)
    osu_ls = []
    for file in path.rglob("*.osu"):
        osu = OsuMap.read_file(str(file.absolute()))
        if options.rate:
            if osu.audio_file_name != audio_file_name:
                continue
            for rate in np.arange(options.rate, end, options.step):
                rate = round(rate, 2)
                osu_new = osu.rate(rate)
                osu_new.version += f" x{rate}"
                osu_new.audio_file_name = audio_name + f"x{rate:.2f}" + audio_type
                osu_ls.append([file.stem + f"x{rate}", osu_new])
        else:
            osu_new = osu.rate(1)
            osu_ls.append([file.stem, osu_new])
    for i in osu_ls:
        if options.fln:
            i[1] = full_ln(i[1], gap=options.gap, ln_as_hit_thres=options.thres)
            i[1].version += " (FULL LN)"
            i[0] += " (FULL LN)"
        if options.nsv:
            i[1].svs = i[1].svs[:0]
            i[1].bpms = i[1].bpms[:1]
            i[1].version += " NSV"
            i[0] += " NSV"
        if options.nln:
            for ln in i[1].holds:
                i[1].hits = i[1].hits.append(OsuHit(ln.offset, int(ln.column)))
            i[1].holds.df = i[1].holds.df[:0]
            i[1].version += " NLN"
            i[0] += " NLN"
        if options.od is not None:
            i[1].overall_difficulty = options.od
            i[1].version += f" OD {options.od}"
            i[0] += f" od{options.od}"
    for filename, osu in osu_ls:
        osu.write_file(path / f"{filename}.osu")

    with ZipFile(path.parent / osz_file.name, "w") as my_zip:
        for file in path.rglob("*"):
            my_zip.write(file, os.path.relpath(file, path))
    shutil.rmtree(path)
    return path.parent / osz_file.name
