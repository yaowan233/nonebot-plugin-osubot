from typing import Optional

from .basemodel import Base
from .user import UserCompact


class Friend(Base):
    """osu! API v2 GET /friends 返回的好友条目。

    示例：
    {
        "target_id": 123,
        "relation_type": "FRIEND",
        "mutual": true,
        "target": { ...UserCompact }
    }
    """

    target_id: int
    relation_type: str = ""
    mutual: bool = False
    target: Optional[UserCompact] = None
