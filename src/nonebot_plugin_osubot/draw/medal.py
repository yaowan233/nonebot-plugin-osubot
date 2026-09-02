"""成就列表渲染（原生 SVG + resvg，网格布局，风格与 friend 一致）。

用于 /ma（已获得成就）与 /ar（成就推荐）的图片输出。
"""

import asyncio

from typing_extensions import TypedDict

from .medal_svg import render_achievement_svg
from .native_assets import image_source_data_uri


class AchievementRenderRow(TypedDict):
    name: str
    icon: str
    grouping: str
    achieved_at: str


class AchievementRenderData(TypedDict):
    me_name: str
    me_avatar: str
    title: str
    subtitle: str
    total: int
    start: int
    end: int
    achievements: list[AchievementRenderRow]


async def draw_achievements(data: AchievementRenderData) -> bytes:
    """本地化头像与图标后渲染成就网格图片。

    Parameters
    ----------
    data : dict
        包含 me_name / me_avatar / title / subtitle / total /
        achievements: list[dict]，每项含 name / icon / grouping / achieved_at(可选)
    """
    achievements = list(data.get("achievements") or [])
    avatar_data, icon_data = await asyncio.gather(
        image_source_data_uri(data.get("me_avatar"), max_size=(156, 156)),
        asyncio.gather(
            *(image_source_data_uri(row.get("icon"), max_size=(144, 144)) for row in achievements)
        ),
    )
    prepared = {
        **data,
        "me_avatar_data": avatar_data,
        "achievements": [
            {**row, "icon_data": prepared_icon} for row, prepared_icon in zip(achievements, icon_data)
        ],
    }
    return await render_achievement_svg(prepared)
