from typing import Optional

from .basemodel import Base


class RecommendItem(Base):
    map_id: int
    mod: int
    mod_str: str
    stars: float
    pred_pp: float
    pred_acc: float
    final_score: float
    title: str
    beatmapset_id: int = 0
    url: Optional[str] = None
    evidence_count: Optional[int] = None
    target: Optional[str] = None


class RecommendSection(Base):
    key: str
    title: str
    items: list[RecommendItem]


class RecommendData(Base):
    player_id: Optional[int] = None
    mode: Optional[str] = None
    target: Optional[str] = None
    recommendations: Optional[list[RecommendItem]] = None
    sections: Optional[list[RecommendSection]] = None
    detail: Optional[str] = None
