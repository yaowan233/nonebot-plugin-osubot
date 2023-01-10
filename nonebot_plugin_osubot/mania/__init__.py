from reamber.algorithms.generate import full_ln
from reamber.osu.OsuMap import OsuMap
from reamber.algorithms.playField import PlayField
from reamber.algorithms.playField.parts import *
from pathlib import Path
from zipfile import ZipFile
from ..file import download_map
import os
import shutil

tmp_path = Path() / "data" / "osu" / "tmp"
if not tmp_path.exists():
    tmp_path.mkdir(parents=True, exist_ok=True)


async def generate_full_ln_osz(set_id: int, gap: float = 150, ln_as_hit_thres: float = 100) -> Path:
    osz_file = await download_map(set_id)
    with ZipFile(osz_file.absolute()) as my_zip:
        my_zip.extractall(tmp_path)
    num = 0
    for file in tmp_path.rglob('*.osu'):
        osu = OsuMap.read_file(str(file.absolute()))
        osu2 = full_ln(osu, gap=gap, ln_as_hit_thres=ln_as_hit_thres)
        osu2.version = osu.version + '(full ln)'
        osu2.write_file(tmp_path / f"{file.stem}(full ln).osu")
        num += 1
    with ZipFile(tmp_path.parent / osz_file.name, 'w') as my_zip:
        for file in tmp_path.rglob('*'):
            my_zip.write(file, os.path.relpath(file, tmp_path))
    shutil.rmtree(tmp_path)
    return tmp_path.parent / osz_file.name


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
