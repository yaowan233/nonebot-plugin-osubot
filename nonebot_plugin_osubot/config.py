from pydantic import Extra, BaseSettings
from typing import Optional


class Config(BaseSettings):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    osz_mirror: Optional[int] = 0


    class Config:
        extra = Extra.ignore
        case_sensitive = False
