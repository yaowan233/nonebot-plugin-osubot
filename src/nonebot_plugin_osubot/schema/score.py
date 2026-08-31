import datetime
from typing import Literal, Optional

from pydantic.fields import Field

from .basemodel import Base
from .user import UserCompact
from .beatmap import Beatmap, Beatmapset, BeatmapCompact, BeatmapsetCompact


class Statistics(Base):
    count_50: Optional[int] = None
    count_100: Optional[int] = None
    count_300: Optional[int] = None
    count_geki: Optional[int] = None
    count_katu: Optional[int] = None
    count_miss: Optional[int] = None


class Score(Base):
    id: Optional[int] = None
    best_id: Optional[int] = None
    user_id: int
    accuracy: float
    mods: list[str]
    score: int
    max_combo: int
    perfect: int
    statistics: Statistics
    passed: bool
    pp: Optional[float] = None
    rank: str
    created_at: str
    mode: Literal["fruits", "mania", "osu", "taiko"]
    mode_int: int
    beatmap: Optional[Beatmap] = None
    beatmapset: Optional[Beatmapset] = None
    match: Optional[dict] = None


class BeatmapUserScore(Base):
    position: int
    score: Score


class NewStatistics(Base):
    great: Optional[int] = Field(default=0)
    slider_tail_hit: Optional[int] = Field(default=0)
    large_tick_hit: Optional[int] = Field(default=0)
    small_tick_hit: Optional[int] = Field(default=0)
    small_tick_miss: Optional[int] = Field(default=0)
    miss: Optional[int] = Field(default=0)
    ok: Optional[int] = Field(default=0)
    meh: Optional[int] = Field(default=0)
    good: Optional[int] = Field(default=0)
    perfect: Optional[int] = Field(default=0)


class Mod(Base):
    acronym: str
    settings: Optional[dict] = None


class NewScore(Base):
    accuracy: float
    beatmap_id: int
    best_id: Optional[int] = None
    build_id: Optional[int] = None
    ended_at: str
    has_replay: bool
    id: int
    is_perfect_combo: bool
    legacy_perfect: bool
    legacy_score_id: Optional[int] = None
    legacy_total_score: Optional[int] = None
    max_combo: int
    maximum_statistics: Optional[dict] = None
    mods: list[Mod]
    passed: bool
    playlist_item_id: Optional[int] = None
    pp: Optional[float] = None
    preserve: bool
    rank: str
    ranked: bool
    room_id: Optional[int] = None
    ruleset_id: int
    started_at: Optional[str] = None
    statistics: Optional[dict] = None
    total_score: int
    type: str
    user_id: int
    # g0v0 的 score.beatmap 是精简 Compact，官方 API 也返回 Compact；
    # 完整难度字段由 draw 层通过 /beatmaps/{id} 单独获取。
    beatmap: Optional[BeatmapCompact] = None
    beatmapset: Optional[BeatmapsetCompact] = None
    # current_user_attributes: Optional[int]
    position: Optional[int] = None
    rank_country: Optional[int] = None
    rank_global: Optional[int] = None
    user: Optional[UserCompact] = None


class UnifiedBeatmap(Base):
    id: int
    set_id: int
    artist: str
    title: str
    version: str
    creator: str
    total_length: int
    mode: int
    bpm: Optional[float] = None
    cs: Optional[float] = None
    od: Optional[float] = None
    ar: Optional[float] = None
    hp: Optional[float] = None
    stars: Optional[float] = None
    checksum: Optional[str] = None
    user_id: Optional[int] = None
    convert: Optional[bool] = False
    status: Optional[str] = None
    is_scoreable: Optional[bool] = None
    max_combo: Optional[int] = None
    count_circles: Optional[int] = None
    count_sliders: Optional[int] = None
    count_spinners: Optional[int] = None


class UnifiedScore(Base):
    mods: list[Mod]
    ruleset_id: int
    rank: str
    accuracy: float
    total_score: int
    legacy_total_score: Optional[int] = None
    ended_at: datetime.datetime
    max_combo: int
    statistics: NewStatistics
    beatmap: Optional[UnifiedBeatmap] = None
    passed: bool
    pp: Optional[float] = None
    # g0v0 的 score.beatmapset 是精简对象，统一用 Compact 类型承载。
    beatmapset: Optional[BeatmapsetCompact] = None
    score_version: Optional[Literal["stable", "lazer"]] = None
    score_id: Optional[int] = None
    user_id: Optional[int] = None


def get_score_version(legacy_score_id: Optional[int]) -> Literal["stable", "lazer"]:
    """Return the official client generation that submitted a score."""
    return "stable" if legacy_score_id is not None else "lazer"
