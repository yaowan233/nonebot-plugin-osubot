from typing import Literal, Optional

from .basemodel import Base


class Badge(Base):
    awarded_at: str
    description: str
    image_url: str
    url: str


class GradeCounts(Base):
    ssh: int
    ss: int
    sh: int
    s: int
    a: int


class Level(Base):
    current: int
    progress: int


class UserStatistics(Base):
    grade_counts: GradeCounts
    hit_accuracy: float
    is_ranked: bool
    level: Level
    maximum_combo: int
    play_count: int
    play_time: int
    pp: int
    ranked_score: int
    replays_watched_by_others: int
    total_hits: int
    total_score: int
    global_rank: Optional[int]
    country_rank: Optional[int]
    badges: Optional[list[Badge]]


class UserCompact(Base):
    avatar_url: str
    country_code: str
    default_group: str
    id: int
    is_active: bool
    is_bot: bool
    is_deleted: bool
    is_online: bool
    is_supporter: bool
    last_visit: Optional[str]
    profile_colour: Optional[str]
    username: str
    statistics: Optional[UserStatistics]


class User(UserCompact):
    cover_url: Optional[str]
    has_supported: Optional[bool]
    join_date: Optional[str]
    location: Optional[str]
    occupation: Optional[str]
    playmode: Optional[Literal["fruits", "mania", "osu", "taiko"]]
    playstyle: Optional[list[str]]
    badges: Optional[list[Badge]]
