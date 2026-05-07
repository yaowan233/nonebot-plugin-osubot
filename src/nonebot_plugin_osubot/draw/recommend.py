from pathlib import Path

from nonebot_plugin_htmlrender import template_to_pic

from ..schema.alphaosu import RecommendData

template_path = str(Path(__file__).parent / "templates")


async def draw_recommend(data: RecommendData, username: str, avatar_url: str) -> bytes:
    pic = await template_to_pic(
        template_path,
        "recommend.html",
        {
            "player_id": data.player_id,
            "mode": data.mode,
            "username": username,
            "avatar_url": avatar_url,
            "recommendations": [item.model_dump() for item in data.recommendations] if data.recommendations else [],
        },
    )
    return pic
