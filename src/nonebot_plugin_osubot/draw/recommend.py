"""推荐谱面面板渲染（原生 SVG + resvg，版式为 design/recommend 概念 B）。

封面复用 map_path/{set_id}/cover.jpg 磁盘缓存（与 bp 卡片共享），头像复用
好友列表的专用缓存；资源失败时使用本地占位图，保证没有网络等待也能出图。
"""

import asyncio
import re

from ..file import get_pfm_img, map_path
from ..schema.alphaosu import RecommendData
from .friend import _load_avatar_data_uri, _placeholder_avatar_data_uri
from .map_render import remote_image_data_uri
from .recommend_svg import render_recommend_svg
from .svg_render import thumbnail_data_uri

SECTION_TITLES = {
    "overall": "综合推荐",
    "hard": "进阶推荐",
    "medium": "稳健推荐",
    "easy": "基础推荐",
}

SIDE_SECTION_ORDER = {"easy": 0, "medium": 1, "hard": 2}

_AVATAR_UID = re.compile(r"a\.ppy\.sh/(\d+)")
# 封面显示尺寸 96x72，按 2x 准备缩略图
_COVER_THUMBNAIL = {"max_width": 192, "max_height": 144}


async def _cover_data_uri(set_id: int) -> str | None:
    """按谱面组读取/下载封面并返回缩略 data URI；失败返回 None 由布局画占位。"""
    if not set_id:
        return None
    cover_path = map_path / str(set_id) / "cover.jpg"
    try:
        if not cover_path.exists():
            await get_pfm_img(f"https://assets.ppy.sh/beatmaps/{set_id}/covers/cover.jpg", cover_path)
        if cover_path.exists() and cover_path.stat().st_size > 0:
            return await asyncio.to_thread(thumbnail_data_uri, cover_path, **_COVER_THUMBNAIL)
    except Exception:
        return None
    return None


async def _player_avatar(avatar_url: str) -> str:
    """头像本地化；a.ppy.sh 地址走好友列表的磁盘缓存，其余直接下载，失败用占位图。"""
    match = _AVATAR_UID.search(avatar_url or "")
    if match:
        return await _load_avatar_data_uri(int(match.group(1)), avatar_url)
    try:
        return await remote_image_data_uri(avatar_url)
    except Exception:
        return _placeholder_avatar_data_uri()


async def draw_recommend(data: RecommendData, username: str, avatar_url: str) -> bytes:
    sections = [
        {
            "key": section.key,
            "title": SECTION_TITLES.get(section.key, section.title),
            "items": [item.model_dump() for item in section.items],
        }
        for section in data.sections or []
    ]
    overall_section = next((section for section in sections if section["key"] == "overall"), None)
    side_sections = sorted(
        [section for section in sections if section["key"] != "overall" and section["items"]],
        key=lambda section: SIDE_SECTION_ORDER.get(section["key"], 99),
    )
    flat_items = [item.model_dump() for item in data.recommendations] if data.recommendations else []

    all_items = [item for section in sections for item in section["items"]] or flat_items

    # ── 资源准备：封面按谱面组去重并发下载，头像并发 ──
    set_ids = sorted({item.get("beatmapset_id") or 0 for item in all_items})
    cover_results, avatar = await asyncio.gather(
        asyncio.gather(*(_cover_data_uri(set_id) for set_id in set_ids)),
        _player_avatar(avatar_url),
    )
    covers = dict(zip(set_ids, cover_results))

    def card_item(item: dict) -> dict:
        return {
            "title": item.get("title", ""),
            "map_id": item.get("map_id", 0),
            "stars": item.get("stars", 0),
            "mod_str": item.get("mod_str", "NM"),
            "pred_pp": item.get("pred_pp", 0),
            "pred_acc": item.get("pred_acc", 0),
            "cover": covers.get(item.get("beatmapset_id") or 0),
        }

    if overall_section is not None:
        shown_sections = [overall_section, *side_sections]
        total_count = sum(len(section["items"]) for section in shown_sections)
        payload = {
            "overall": {"title": overall_section["title"], "items": [card_item(i) for i in overall_section["items"]]},
            "side": [
                {"key": section["key"], "title": section["title"], "items": [card_item(i) for i in section["items"]]}
                for section in side_sections
            ],
            "flat": None,
            "total_count": total_count,
            "section_titles": [section["title"] for section in shown_sections],
        }
    else:
        payload = {
            "overall": None,
            "side": [],
            "flat": [card_item(item) for item in flat_items],
            "total_count": len(flat_items),
            "section_titles": ["推荐列表"],
        }

    payload.update(
        {
            "username": username,
            "player_id": data.player_id,
            "mode": data.mode or "osu",
            "avatar": avatar,
        }
    )
    return await render_recommend_svg(payload)
