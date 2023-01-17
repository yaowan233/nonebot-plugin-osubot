from reamber.algorithms.generate import full_ln
from reamber.osu.OsuMap import OsuMap
from reamber.algorithms.playField import PlayField
from reamber.algorithms.playField.parts import *
from pathlib import Path
from zipfile import ZipFile
from ..file import download_map
import os
import shutil
import asyncio

osu_path = Path() / "data" / "osu"
if not osu_path.exists():
    osu_path.mkdir(parents=True, exist_ok=True)


async def generate_full_ln_osz(set_id: int, gap: float = 150, ln_as_hit_thres: float = 100) -> Path:
    path = osu_path / f"{set_id}"
    osz_file = await download_map(set_id)
    with ZipFile(osz_file.absolute()) as my_zip:
        my_zip.extractall(path / f"")
    os.remove(osz_file)
    num = 0
    for file in path.rglob('*.osu'):
        osu = OsuMap.read_file(str(file.absolute()))
        osu2 = full_ln(osu, gap=gap, ln_as_hit_thres=ln_as_hit_thres)
        osu2.version = osu.version + '(full ln)'
        osu2.write_file(path / f"{file.stem}(full ln).osu")
        num += 1
    with ZipFile(path.parent / osz_file.name, 'w') as my_zip:
        for file in path.rglob('*'):
            my_zip.write(file, os.path.relpath(file, path))
    shutil.rmtree(path)
    return path.parent / osz_file.name


async def generate_preview_pic(file: Path):
    m = OsuMap.read_file(str(file.absolute()))
    pf = (
            PlayField(m, padding=30)
            + PFDrawColumnLines()
            + PFDrawBeatLines()
            + PFDrawBpm(x_offset=30, y_offset=0)
            + PFDrawSv(y_offset=0)
            + PFDrawNotes()
    )
    pf.export_fold(max_height=1000).save("data/osu/preview.png")
    return Path("data/osu/preview.png")


async def change_rate(set_id: int, rate: float = 1.1):
    path = osu_path / f"{set_id}"
    osz_file = await download_map(set_id)
    with ZipFile(osz_file.absolute()) as my_zip:
        my_zip.extractall(path)
    os.remove(osz_file)
    processed = []
    osu_ls = []
    for file in path.rglob('*.osu'):
        osu = OsuMap.read_file(str(file.absolute()))
        osu2 = osu.rate(rate)
        osu2.version = osu.version + f' x{rate}'
        osu2.audio_file_name = osu.audio_file_name.rstrip('.mp3') + f'x{rate}.mp3'
        audio_path = path / osu.audio_file_name
        osu_ls.append((file, osu2))
        if audio_path in processed:
            continue
        else:
            processed.append(audio_path)

        new_audio_path = path / osu2.audio_file_name
        proc = await asyncio.create_subprocess_shell(
            f'ffmpeg -i "{audio_path.absolute()}" -filter_complex [0:a]atempo={rate}[s0] -map [s0] '
            f'"{new_audio_path.absolute()}" -loglevel quiet'
        )
        await proc.wait()
    for file, osu in osu_ls:
        osu.write_file(path / f"{file.stem}x{rate}.osu")

    with ZipFile(path.parent / osz_file.name, 'w') as my_zip:
        for file in path.rglob('*'):
            my_zip.write(file, os.path.relpath(file, path))
    shutil.rmtree(path)
    return path.parent / osz_file.name
