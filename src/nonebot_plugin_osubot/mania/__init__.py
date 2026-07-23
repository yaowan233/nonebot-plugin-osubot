import os
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
from vsrg_tools.osu.OsuMap import OsuMap
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
        inset = 3
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
    m = OsuMap.read_file(str(file.absolute()))
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
