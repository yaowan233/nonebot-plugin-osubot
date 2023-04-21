from typing import List, Optional

from .basemodel import Base


class ListData(Base):
    accurate: bool
    currentMod: Optional[List[str]]
    currentPP: Optional[int]
    currentScore: Optional[int]
    currentScoreLink: Optional[str]
    difficulty: float
    id: str
    mapCoverUrl: str
    mapLink: str
    mapName: str
    mod: List[str]
    newRecordPercent: float
    passPercent: float
    ppIncrement: float
    ppIncrementExpect: float
    predictPP: float


class Data(Base):
    next: int
    prev: int
    total: int
    list: List[ListData]


class RecommendData(Base):
    code: int
    message: str
    success: bool
    data: Optional[Data]
