from typing import Optional
from .basemodel import Base


class BidData(Base):
    id: int
    mode_int: int
    version: str
    total_length: int
    cs: float
    ar: float
    accuracy: float
    drain: float
    difficulty_rating: float
    count_circles: int
    count_sliders: int
    count_spinners: int
    max_combo: Optional[int] = None
    playcount: int
    passcount: int


class BeatmapSets(Base):
    id: int
    ranked: int
    title: str
    artist: str
    title_unicode: str
    artist_unicode: str
    creator: str
    user_id: int
    source: str
    last_updated: str
    ranked_date: Optional[str]
    bpm: float
    favourite_count: int
    video: bool
    storyboard: bool
    tags: str
    language_id: int
    genre_id: int
    beatmaps: list[BidData]
