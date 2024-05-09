from typing import Literal, Optional

from .basemodel import Base
from .beatmap import Beatmap, Beatmapset


class Statistics(Base):
    count_50: Optional[int]
    count_100: Optional[int]
    count_300: Optional[int]
    count_geki: Optional[int]
    count_katu: Optional[int]
    count_miss: Optional[int]


class Score(Base):
    id: int
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


class BeatmapUserScore(Base):
    position: int
    score: Score


class NewStatistics(Base):
    great: Optional[int]
    large_tick_hit: Optional[int]
    small_tick_hit: Optional[int]
    small_tick_miss: Optional[int]
    miss: Optional[int]
    ok: Optional[int]
    meh: Optional[int]
    good: Optional[int]
    perfect: Optional[int]


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
    mods: list[dict]
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


