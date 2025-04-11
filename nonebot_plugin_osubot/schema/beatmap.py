from typing import Literal, Optional

from .user import User
from .basemodel import Base


class Covers(Base):
    cover: str
    card: str
    list: str
    slimcover: str


class Gds(Base):
    id: int
    username: str


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
    beatmapset_id: Optional[int] = None
    user_id: int
    status: str
    video: bool
    converts: Optional[str] = None
    description: Optional[str] = None
    has_favourited: Optional[bool] = None
    language: Optional[str] = None
    user: Optional[User] = None
    total_length: Optional[int] = None


class Beatmapset(BeatmapsetCompact):
    bpm: Optional[float] = None
    can_be_hyped: Optional[bool] = None
    ranked: Optional[int] = None
    ranked_date: Optional[str] = None
    tags: Optional[str] = None


class BeatmapCompact(Base):
    beatmapset_id: int
    difficulty_rating: float
    id: int
    mode: Literal["fruits", "mania", "osu", "taiko"]
    status: str
    total_length: float
    user_id: int
    version: str
    beatmapset: Optional[Beatmapset] = None
    checksum: Optional[str] = None
    max_combo: Optional[int] = None
    version: str


class Beatmap(BeatmapCompact):
    accuracy: float
    ar: float
    bpm: Optional[float] = None
    convert: bool
    count_circles: int
    count_sliders: int
    count_spinners: int
    cs: float
    deleted_at: Optional[str] = None
    drain: float
    hit_length: int
    is_scoreable: bool
    last_updated: str
    mode_int: int
    passcount: int
    playcount: int
    ranked: int
    url: str
    owners: Optional[list[Gds]] = None


class BackgroundsAttributes(Base):
    url: str
    user: dict


class SeasonalBackgrounds(Base):
    ends_at: str
    backgrounds: list[BackgroundsAttributes]
