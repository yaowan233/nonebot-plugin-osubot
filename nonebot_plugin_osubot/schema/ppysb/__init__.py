from typing import Optional

from pydantic import BaseModel


class Beatmap(BaseModel):
    md5: str
    id: int
    set_id: int
    artist: str
    title: str
    version: str
    creator: str
    last_update: str
    total_length: int
    max_combo: int
    status: int
    plays: int
    passes: int
    mode: int
    bpm: float
    cs: float
    od: float
    ar: float
    hp: float
    diff: float


class Score(BaseModel):
    id: int
    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int
    n300: Optional[int] = 0
    n100: Optional[int] = 0
    n50: Optional[int] = 0
    nmiss: Optional[int] = 0
    ngeki: Optional[int] = 0
    nkatu: Optional[int] = 0
    grade: str
    status: int
    mode: int
    play_time: str
    time_elapsed: int
    perfect: int
    beatmap: Optional[Beatmap] = None


class ScoresResponse(BaseModel):
    status: str
    scores: list[Score]


class V2ScoresResponse(BaseModel):
    status: str
    data: list[Score]


class Info(BaseModel):
    id: int
    name: str
    safe_name: str
    priv: int
    country: str
    silence_end: int
    donor_end: int
    creation_time: int
    latest_activity: int
    clan_id: int
    clan_priv: int
    preferred_mode: int
    play_style: int


class Player(BaseModel):
    info: Info
    stats: dict


class InfoResponse(BaseModel):
    status: str
    player: Player
