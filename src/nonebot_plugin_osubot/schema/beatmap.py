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
    """谱面精简对象。

    官方 osu! API 的 compact 包含完整难度字段；g0v0 的 score.beatmap 是更精简的
    子集（缺 cs/ar/od/bpm/count_* 等）。为兼容 g0v0，全部难度字段放宽为 Optional，
    缺失值由上游 draw 层通过 /beatmaps/{id} 完整谱面兜底。
    """

    beatmapset_id: Optional[int] = None
    difficulty_rating: Optional[float] = None
    id: int
    mode: Optional[Literal["fruits", "mania", "osu", "taiko"]] = None
    status: Optional[str] = None
    total_length: Optional[float] = None
    user_id: Optional[int] = None
    version: Optional[str] = None
    beatmapset: Optional[Beatmapset] = None
    checksum: Optional[str] = None
    max_combo: Optional[int] = None
    accuracy: Optional[float] = None
    ar: Optional[float] = None
    bpm: Optional[float] = None
    convert: Optional[bool] = None
    count_circles: Optional[int] = None
    count_sliders: Optional[int] = None
    count_spinners: Optional[int] = None
    cs: Optional[float] = None
    drain: Optional[float] = None
    hit_length: Optional[int] = None
    is_scoreable: Optional[bool] = None
    last_updated: Optional[str] = None
    mode_int: Optional[int] = None
    passcount: Optional[int] = None
    playcount: Optional[int] = None
    ranked: Optional[int] = None
    url: Optional[str] = None


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
