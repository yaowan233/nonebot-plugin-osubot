from typing import Optional

from .basemodel import Base


class ListData(Base):
    accurate: bool
    currentMod: Optional[list[str]] = None
    currentPP: Optional[int] = None
    currentScore: Optional[int] = None
    currentScoreLink: Optional[str] = None
    difficulty: float
    id: str
    mapCoverUrl: str
    mapLink: str
    mapName: str
    mod: list[str]
    newRecordPercent: float
    passPercent: float
    ppIncrement: float
    ppIncrementExpect: float
    predictPP: float


class Data(Base):
    next: int
    prev: int
    total: int
    list: list[ListData]


class RecommendData(Base):
    code: int
    message: str
    success: bool
    data: Optional[Data] = None
