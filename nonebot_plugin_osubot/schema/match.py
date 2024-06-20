from typing import Optional

from .basemodel import Base
from .beatmap import BeatmapCompact
from .score import Score
from .user import User


class Game(Base):
    beatmap_id: int
    mods: list[str]
    beatmap: BeatmapCompact
    scores: list[Score]
    team_type: str


class Detail(Base):
    type: str


class Event(Base):
    id: int
    game: Optional[Game]
    detail: Detail
    timestamp: str


class Match(Base):
    match: dict
    events: list[Event]
    users: list[User]
