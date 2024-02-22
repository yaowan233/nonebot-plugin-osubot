from pydantic import BaseModel
from typing import Optional, List, Union


class Config(BaseModel):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    osz_mirror: Optional[int] = 0
    info_bg: Optional[List[str]] = ["https://api.hiosu.com/erciyuan/302.php"]
    osu_proxy: Optional[Union[str, dict]] = None
