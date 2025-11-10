from typing import Optional

from pydantic import BaseModel

from .user import Badge, Level, GradeCounts


class Statistics(BaseModel):
    """用户统计数据"""

    level: Level
    global_rank: Optional[int] = None  # 全球排名
    global_rank_percent: Optional[float] = None  # 全球排名百分比
    country_rank: Optional[int] = None  # 国家/地区排名
    pp: float
    grade_counts: GradeCounts
    ranked_score: int
    hit_accuracy: float
    play_count: int
    total_score: int
    total_hits: int
    play_time: int
    maximum_combo: int
    replays_watched_by_others: int


class Team(BaseModel):
    """用户战队信息（为绘图用途专门创建的模型，若无数据则为 null）"""

    name: str
    flag_url: str

    # 启用 extra="allow" 可以允许接收更多未定义的字段
    class Config:
        extra = "allow"


class DrawUser(BaseModel):
    """Osu! 用户信息根模型"""

    id: int
    username: str
    country_code: str  # e.g., "AU"
    team: Optional[Team] = None
    footer: str  # e.g., "2025/11/07 14:11:45 | 数据对比于4天前"
    mode: str  # e.g., "STD"
    badges: Optional[list[Badge]] = None
    statistics: Optional[Statistics] = None
    rank_change: Optional[str] = None
    country_rank_change: Optional[str] = None
    pp_change: Optional[str] = None
    acc_change: Optional[str] = None
    pc_change: Optional[str] = None
    hits_change: Optional[str] = None
