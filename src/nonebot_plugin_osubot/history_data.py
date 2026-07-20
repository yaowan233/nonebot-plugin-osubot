from __future__ import annotations

import datetime
from typing import Iterable

from expiringdict import ExpiringDict
from nonebot import get_plugin_config
from nonebot.log import logger

from .api import safe_async_get
from .config import Config

HistoryPoint = tuple[float, str, int]

plugin_config = get_plugin_config(Config)
history_cache: ExpiringDict = ExpiringDict(max_len=256, max_age_seconds=600)


async def get_osutrack_history(user_id: int, mode: int, days: int = 0) -> list[HistoryPoint]:
    """Fetch daily read-only snapshots from osu!track."""
    if not plugin_config.osutrack_enabled or mode not in {0, 1, 2, 3}:
        return []

    query_days = days if days > 0 else max(plugin_config.osutrack_default_days, 1)
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=query_days)
    cache_key = (user_id, mode, start_date.isoformat(), end_date.isoformat())
    cached = history_cache.get(cache_key)
    if cached is not None:
        return list(cached)

    response = await safe_async_get(
        "https://osutrack-api.ameo.dev/stats_history",
        params={
            "user": user_id,
            "mode": mode,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
        },
    )
    if response.status_code == 404:
        return []
    if response.status_code != 200:
        raise RuntimeError(f"osu!track 返回状态码 {response.status_code}")

    daily: dict[str, HistoryPoint] = {}
    for item in response.json():
        try:
            date = str(item["timestamp"])[:10]
            point = (float(item["pp_raw"]), date, int(item["pp_rank"]))
        except (KeyError, TypeError, ValueError):
            continue
        if point[2] > 0:
            daily[date] = point

    result = [daily[date] for date in sorted(daily)]
    history_cache[cache_key] = result
    return result


async def merge_osutrack_history(
    user_id: int,
    mode: int,
    local_points: Iterable[HistoryPoint],
    days: int = 0,
) -> tuple[list[HistoryPoint], bool]:
    """Merge external history with local snapshots, preferring local data on duplicate dates."""
    local_by_date = {str(date): (float(pp), str(date), int(rank)) for pp, date, rank in local_points if rank}
    external_points: list[HistoryPoint] = []
    try:
        external_points = await get_osutrack_history(user_id, mode, days)
    except Exception as error:
        logger.warning(f"获取 osu!track 历史失败，使用本地数据: {error}")

    merged = {date: (pp, date, rank) for pp, date, rank in external_points}
    external_dates = set(merged) - set(local_by_date)
    merged.update(local_by_date)
    return [merged[date] for date in sorted(merged)], bool(external_dates)


def clear_history_cache() -> None:
    history_cache.clear()
