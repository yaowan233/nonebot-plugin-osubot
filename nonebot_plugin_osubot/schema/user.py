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


class Variant(Base):
    mode: str
    variant: str
    country_rank: Optional[int] = None
    global_rank: Optional[int] = None
    pp: Optional[float] = None


class UserStatistics(Base):
    grade_counts: GradeCounts
    hit_accuracy: float
    is_ranked: bool
    level: Level
    maximum_combo: int
    play_count: int
    play_time: int
    pp: float
    ranked_score: int
    replays_watched_by_others: int
    total_hits: int
    total_score: int
    global_rank: Optional[int] = None
    country_rank: Optional[int] = None
    badges: Optional[list[Badge]] = None
    variants: Optional[list[Variant]] = None


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
    last_visit: Optional[str] = None
    profile_colour: Optional[str] = None
    username: str
    statistics: Optional[UserStatistics] = None


class StatisticsRulesets(Base):
    osu: Optional[UserStatistics] = None
    taiko: Optional[UserStatistics] = None
    fruits: Optional[UserStatistics] = None
    mania: Optional[UserStatistics] = None


class User(UserCompact):
    cover_url: Optional[str] = None
    has_supported: Optional[bool] = None
    join_date: Optional[str] = None
    location: Optional[str] = None
    occupation: Optional[str] = None
    playmode: Optional[Literal["fruits", "mania", "osu", "taiko"]] = None
    playstyle: Optional[list[str]] = None
    badges: Optional[list[Badge]] = None
    statistics_rulesets: Optional[StatisticsRulesets] = None
