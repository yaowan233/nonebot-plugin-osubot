from typing import Literal, Optional

from pydantic.fields import Field

from .basemodel import Base
from .user import UserCompact
from .beatmap import Beatmap, Beatmapset


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
    large_tick_hit: Optional[int] = Field(default=0)
    small_tick_hit: Optional[int] = Field(default=0)
    small_tick_miss: Optional[int] = Field(default=0)
    miss: Optional[int] = Field(default=0)
    ok: Optional[int] = Field(default=0)
    meh: Optional[int] = Field(default=0)
    good: Optional[int] = Field(default=0)
    perfect: Optional[int] = Field(default=0)


class Settings(Base):
    speed_change: Optional[float] = None
    circle_size: Optional[float] = None
    approach_rate: Optional[float] = None
    overall_difficulty: Optional[float] = None
    drain_rate: Optional[float] = None


class Mod(Base):
    acronym: str
    settings: Optional[Settings] = None


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
    legacy_total_score: int
    max_combo: int
    maximum_statistics: Optional[Statistics] = None
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
    statistics: Optional[NewStatistics] = None
    total_score: int
    type: str
    user_id: int
    beatmap: Optional[Beatmap] = None
    beatmapset: Optional[Beatmapset] = None
    # current_user_attributes: Optional[int]
    position: Optional[int] = None
    rank_country: Optional[int] = None
    rank_global: Optional[int] = None
    user: Optional[UserCompact] = None
