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
    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int
    grade: str
    status: int
    mode: int
    play_time: str
    time_elapsed: int
    perfect: int
    beatmap: Beatmap


class ScoresResponse(BaseModel):
    status: str
    scores: list[Score]
