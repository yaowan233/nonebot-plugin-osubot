from typing import Optional, List, Union

from pydantic import field_validator

from .user import User
from .score import Score
from .basemodel import Base
from .beatmap import BeatmapCompact


class Game(Base):
    beatmap_id: int
    # 【修改点 1】mods 兼容 str 和 dict/Mod 对象
    mods: List[Union[str, dict]] = []
    
    beatmap: BeatmapCompact
    scores: list[Score]
    team_type: str

    # 【新增验证器】统一处理 game 级别的 mods
    @field_validator('mods', mode='before')
    @classmethod
    def parse_mods(cls, v):
        if not v:
            return []
        
        result = []
        for m in v:
            if isinstance(m, dict):
                result.append(m.get('acronym', ''))
            elif isinstance(m, str):
                result.append(m)
            else:
                result.append(getattr(m, 'acronym', str(m)))
        return result


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