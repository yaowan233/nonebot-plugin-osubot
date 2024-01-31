from typing import List, Literal, Optional

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
    mods: List[str]
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
