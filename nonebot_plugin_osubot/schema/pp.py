from typing import Optional
from .basemodel import Base


class PP(Base):
    StarRating: float
    HP: Optional[float]
    CS: Optional[float]
    Aim: Optional[int]
    Speed: Optional[int]
    AR: Optional[float]
    OD: Optional[float]
    aim: Optional[int]
    speed: Optional[int]
    accuracy: Optional[int]
    flashlight: Optional[int]
    effective_miss_count: Optional[int]
    pp: int
    ifpp: int
    sspp: int
