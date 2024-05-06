from pydantic import BaseModel
from typing import Optional, Union


class Config(BaseModel):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    info_bg: Optional[list[str]] = ["https://api.hiosu.com/erciyuan/pe.php"]
    osu_proxy: Optional[Union[str, dict]] = None
