from dataclasses import dataclass

from expiringdict import ExpiringDict
from nonebot.internal.adapter import Event

from ..api import osu_api


@dataclass(slots=True)
class BeatmapContext:
    map_id: str | None = None
    set_id: str | None = None


_contexts: ExpiringDict = ExpiringDict(max_len=10000, max_age_seconds=30 * 60)


def _context_key(event: Event) -> str:
    adapter_scope = f"{event.__class__.__module__}:{getattr(event, 'self_id', '')}"
    if group_id := getattr(event, "group_id", None):
        return f"{adapter_scope}:group:{group_id}"
    if channel_id := getattr(event, "channel_id", None):
        guild_id = getattr(event, "guild_id", None)
        return f"{adapter_scope}:channel:{guild_id}:{channel_id}"
    return f"{adapter_scope}:private:{event.get_session_id()}"


def remember_map(event: Event, map_id: int | str, set_id: int | str | None = None) -> None:
    """Remember a beatmap, preserving its known set id when refreshing the same map."""
    key = _context_key(event)
    normalized_map_id = str(map_id)
    context = _contexts.get(key)
    preserved_set_id = context.set_id if context and context.map_id == normalized_map_id else None
    _contexts[key] = BeatmapContext(
        map_id=normalized_map_id,
        set_id=str(set_id) if set_id is not None else preserved_set_id,
    )


def remember_set(event: Event, set_id: int | str) -> None:
    """Remember a beatmapset, preserving its known map id when refreshing the same set."""
    key = _context_key(event)
    normalized_set_id = str(set_id)
    context = _contexts.get(key)
    preserved_map_id = context.map_id if context and context.set_id == normalized_set_id else None
    _contexts[key] = BeatmapContext(map_id=preserved_map_id, set_id=normalized_set_id)


def remember_map_and_set(event: Event, map_id: int | str, set_id: int | str) -> None:
    _contexts[_context_key(event)] = BeatmapContext(map_id=str(map_id), set_id=str(set_id))


def get_last_map_id(event: Event) -> str | None:
    context = _contexts.get(_context_key(event))
    return context.map_id if context else None


async def get_last_set_id(event: Event) -> str | None:
    key = _context_key(event)
    context = _contexts.get(key)
    if not context:
        return None
    if context.set_id:
        return context.set_id
    if not context.map_id:
        return None

    data = await osu_api("map", map_id=int(context.map_id))
    context.set_id = str(data["beatmapset_id"])
    _contexts[key] = context
    return context.set_id


def clear_contexts() -> None:
    """Clear cached contexts; intended for tests."""
    _contexts.clear()
