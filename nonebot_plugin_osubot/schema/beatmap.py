from typing import Optional, Literal

from .basemodel import Base
from .user import User


class Covers(Base):
    cover: str
    card: str
    list: str
    slimcover: str


class BeatmapsetCompact(Base):
    artist: str
    artist_unicode: str
    covers: Covers
    creator: str
    favourite_count: int
    id: int
    nsfw: bool
    play_count: int
    preview_url: str
    source: str
    title: str
    title_unicode: str
    beatmapset_id: Optional[int]
    user_id: int
    status: str
    video: bool
    converts: Optional[str]
    description: Optional[str]
    has_favourited: Optional[bool]
    language: Optional[str]
    user: Optional[User]
    total_length: Optional[int]


class Beatmapset(BeatmapsetCompact):
    bpm: Optional[float]
    can_be_hyped: Optional[bool]
    ranked: Optional[int]
    ranked_date: Optional[str]
    tags: Optional[str]


class BeatmapCompact(Base):
    beatmapset_id: int
    difficulty_rating: float
    id: int
    mode: Literal["fruits", "mania", "osu", "taiko"]
    status: str
    total_length: float
    user_id: int
    version: str
    beatmapset: Optional[Beatmapset]
    checksum: Optional[str]
    max_combo: Optional[int]
    version: str


class Beatmap(BeatmapCompact):
    accuracy: float
    ar: float
    bpm: Optional[float]
    convert: bool
    count_circles: int
    count_sliders: int
    count_spinners: int
    cs: float
    deleted_at: Optional[str]
    drain: float
    hit_length: int
    is_scoreable: bool
    last_updated: str
    mode_int: int
    passcount: int
    playcount: int
    ranked: int
    url: str


class BackgroundsAttributes(Base):
    url: str
    user: dict


class SeasonalBackgrounds(Base):
    ends_at: str
    backgrounds: list[BackgroundsAttributes]
