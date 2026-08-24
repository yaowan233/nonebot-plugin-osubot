from typing import Optional

from pydantic import Field

try:
    from pydantic import field_validator

    def _before_validator(field: str):
        return field_validator(field, mode="before")

except ImportError:  # Pydantic v1
    from pydantic import validator

    def _before_validator(field: str):
        return validator(field, pre=True, allow_reuse=True)


from .user import User
from .score import Score
from .basemodel import Base
from .beatmap import BeatmapCompact


def normalize_mods(value) -> list[str]:
    """Normalize legacy strings and lazer mod objects to acronym strings."""
    if not value:
        return []

    result: list[str] = []
    for mod in value:
        acronym = (
            mod.get("acronym")
            if isinstance(mod, dict)
            else mod
            if isinstance(mod, str)
            else getattr(mod, "acronym", None)
        )
        if acronym:
            result.append(str(acronym))
    return result


class Game(Base):
    beatmap_id: int
    mods: list[str] = Field(default_factory=list)

    beatmap: BeatmapCompact
    scores: list[Score]
    team_type: str

    @_before_validator("mods")
    @classmethod
    def parse_mods(cls, v):
        return normalize_mods(v)


class Detail(Base):
    type: str


class Event(Base):
    id: int
    game: Optional[Game] = None
    detail: Detail
    timestamp: str


class Match(Base):
    match: dict
    events: list[Event]
    users: list[User]
