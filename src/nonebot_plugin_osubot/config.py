from pathlib import Path
from typing import Union, Optional

from pydantic import BaseModel


class Config(BaseModel):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    info_bg: Optional[list[str]] = ["https://t.alcy.cc/mp", "https://t.alcy.cc/moemp"]
    osu_proxy: Optional[Union[str, dict]] = None
    osutrack_enabled: bool = True
    osutrack_default_days: int = 365
    osu_preview_taiko_skin_path: Optional[Path] = None
    osu_preview_ffmpeg_path: Optional[Path] = None
    osu_preview_full_scale: float = 0.75
    osu_preview_full_frame_interval: int = 30
    osu_preview_taiko_full_scale: float = 0.5
    osu_preview_taiko_full_frame_interval: int = 30
    osu_preview_std_catch_full_scale: float = 0.5
    osu_preview_std_catch_full_frame_interval: int = 30
