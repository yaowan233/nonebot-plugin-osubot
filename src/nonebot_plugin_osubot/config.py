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
    osu_recommend_api: str = "http://192.168.6.136:8000"
    osu_recommend_timeout: float = 240.0
    osu_recommend_candidate_limit: int = 1000
    osu_recommend_result_limit: int = 10
    osu_preview_taiko_skin_path: Optional[Path] = None
    osu_preview_ffmpeg_path: Optional[Path] = None
    osu_preview_full_scale: float = 0.75
    osu_preview_full_frame_interval: int = 30
    osu_preview_taiko_full_scale: float = 0.5
    osu_preview_taiko_full_frame_interval: int = 30
    osu_preview_std_catch_full_scale: float = 0.5
    osu_preview_std_catch_full_frame_interval: int = 30
