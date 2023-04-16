from pydantic import Extra, BaseSettings
from typing import Optional, List


class Config(BaseSettings):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    osz_mirror: Optional[int] = 0
    info_bg: Optional[List[str]] = ['https://api.ghser.com/random/pe.php']

    class Config:
        extra = Extra.ignore
        case_sensitive = False
