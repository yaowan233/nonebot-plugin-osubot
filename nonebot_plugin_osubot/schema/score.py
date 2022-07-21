from typing import List, Literal, Optional

from .basemodel import Base
from .user import User
from .beatmap import Beatmap, Beatmapset


class Statistics(Base):
    count_50: int
    count_100: int
    count_300: int
    count_geki: int
    count_katu: int
    count_miss: int


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
    mode: Literal['fruits', 'mania', 'osu', 'taiko']
    mode_int: int
    user: User
    beatmap: Beatmap
    beatmapset: Optional[Beatmapset]


class BeatmapUserScore(Base):
    position: int
    score: Score
