from typing import List

from .basemodel import Base


class BidData(Base):
    bid: int
    mode: int
    version: str
    length: int
    CS: float
    AR: float
    OD: float
    HP: float
    star: float
    aim: float
    speed: float
    hit300window: float
    pp: float
    pp_aim: float
    pp_speed: float
    pp_acc: float
    circles: int
    sliders: int
    spinners: int
    maxcombo: int
    playcount: int
    passcount: int


class MapInfo(Base):
    sid: int
    local_update: int
    bids_amount: int
    approved: int
    title: str
    artist: str
    titleU: str
    artistU: str
    creator: str
    creator_id: int
    source: str
    last_update: str
    approved_date: int
    bpm: float
    favourite_count: int
    video: int
    storyboard: int
    tags: str
    language: int
    genre: str
    bid_data: List[BidData]


class SayoBeatmap(Base):
    status: int
    data: MapInfo
