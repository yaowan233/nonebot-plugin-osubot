from pydantic import Extra, BaseSettings
from typing import Optional, List, Union


class Config(BaseSettings):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    osz_mirror: Optional[int] = 0
    info_bg: Optional[List[str]] = ['https://api.gumengya.com/Api/DmImg?format=image']
    osu_proxy: Optional[Union[str, dict]] = None

    class Config:
        extra = Extra.ignore
        case_sensitive = False
