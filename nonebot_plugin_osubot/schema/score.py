from typing import Literal, Optional

from pydantic.fields import Field

from .basemodel import Base
from .beatmap import Beatmap, Beatmapset
from .user import UserCompact


class Statistics(Base):
    count_50: Optional[int]
    count_100: Optional[int]
    count_300: Optional[int]
    count_geki: Optional[int]
    count_katu: Optional[int]
    count_miss: Optional[int]


class Score(Base):
    id: Optional[int]
    best_id: Optional[int]
    user_id: int
    accuracy: float
    mods: list[str]
    score: int
    max_combo: int
    perfect: int
    statistics: Statistics
    passed: bool
    pp: Optional[float]
    rank: str
    created_at: str
    mode: Literal["fruits", "mania", "osu", "taiko"]
    mode_int: int
    beatmap: Optional[Beatmap]
    beatmapset: Optional[Beatmapset]
    match: Optional[dict]


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
    speed_change: Optional[float]
    circle_size: Optional[float]
    approach_rate: Optional[float]
    overall_difficulty: Optional[float]
    drain_rate: Optional[float]


class Mod(Base):
    acronym: str
    settings: Optional[Settings]


class NewScore(Base):
    accuracy: float
    beatmap_id: int
    best_id: Optional[int]
    build_id: Optional[int]
    ended_at: str
    has_replay: bool
    id: int
    is_perfect_combo: bool
    legacy_perfect: bool
    legacy_score_id: Optional[int]
    legacy_total_score: int
    max_combo: int
    maximum_statistics: Optional[Statistics]
    mods: list[Mod]
    passed: bool
    playlist_item_id: Optional[int]
    pp: Optional[float]
    preserve: bool
    rank: str
    ranked: bool
    room_id: Optional[int]
    ruleset_id: int
    started_at: Optional[str]
    statistics: Optional[NewStatistics]
    total_score: int
    type: str
    user_id: int
    beatmap: Optional[Beatmap]
    beatmapset: Optional[Beatmapset]
    # current_user_attributes: Optional[int]
    position: Optional[int]
    rank_country: Optional[int]
    rank_global: Optional[int]
    user: Optional[UserCompact]
