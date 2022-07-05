from pydantic import Extra, BaseSettings
from typing import Optional


class Config(BaseSettings):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None

    class Config:
        extra = Extra.ignore
        case_sensitive = False
