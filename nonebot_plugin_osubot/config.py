from typing import Union, Optional

from pydantic import BaseModel


class Config(BaseModel):
    osu_client: Optional[int] = None
    osu_key: Optional[str] = None
    info_bg: Optional[list[str]] = ["https://t.alcy.cc/mp", "https://t.alcy.cc/moemp"]
    osu_proxy: Optional[Union[str, dict]] = None
