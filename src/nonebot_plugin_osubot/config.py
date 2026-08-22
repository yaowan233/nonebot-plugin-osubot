from pathlib import Path
from typing import Union, Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    osu_proxy: Optional[Union[str, dict]] = None
    osutrack_enabled: bool = True
    osutrack_default_days: int = 365
    osu_recommend_api: str = "https://mayumi.xyz"
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
    osu_preview_bin_path: Optional[Path] = None
    osu_preview_use_core: bool = True
    osu_preview_fallback: bool = True
    osu_preview_timeout: float = 120.0
    osu_preview_video_timeout: float = 300.0
    osu_score_history_enabled: bool = True
    osu_score_history_sync_hour: int = Field(default=2, ge=0, le=23)
    osu_score_history_concurrency: int = Field(default=2, ge=1, le=20)
    osu_score_history_recent_limit: int = Field(default=200, ge=1, le=1000)
    osu_api_max_concurrency: int = Field(default=8, ge=2, le=64)
    osu_api_foreground_rate: float = Field(default=8.0, gt=0, le=100)
    osu_api_background_rate: float = Field(default=1.0, gt=0, le=20)
    osu_api_queue_size: int = Field(default=512, ge=10, le=10000)
    osu_api_max_retries: int = Field(default=3, ge=0, le=10)
    osu_render_max_concurrency: int = Field(default=2, ge=1, le=16)
    osu_render_queue_size: int = Field(default=64, ge=1, le=1000)
    osu_render_queue_timeout: float = Field(default=30.0, gt=0, le=300)
    osu_render_timeout: float = Field(default=180.0, gt=0, le=900)
