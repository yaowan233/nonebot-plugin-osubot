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
    return f"{event.get_session_id()}:{event.get_user_id()}"


def remember_map(event: Event, map_id: int | str, set_id: int | str | None = None) -> None:
    """Remember a beatmap and discard any set id that may belong to an older map."""
    _contexts[_context_key(event)] = BeatmapContext(
        map_id=str(map_id),
        set_id=str(set_id) if set_id is not None else None,
    )


def remember_set(event: Event, set_id: int | str) -> None:
    """Remember a beatmapset and discard any map id from an older set."""
    _contexts[_context_key(event)] = BeatmapContext(set_id=str(set_id))


def remember_map_and_set(event: Event, map_id: int | str, set_id: int | str) -> None:
    _contexts[_context_key(event)] = BeatmapContext(map_id=str(map_id), set_id=str(set_id))


def get_last_map_id(event: Event) -> str | None:
    context = _contexts.get(_context_key(event))
    return context.map_id if context else None


async def get_last_set_id(event: Event) -> str | None:
    context = _contexts.get(_context_key(event))
    if not context:
        return None
    if context.set_id:
        return context.set_id
    if not context.map_id:
        return None

    data = await osu_api("map", map_id=int(context.map_id))
    context.set_id = str(data["beatmapset_id"])
    _contexts[_context_key(event)] = context
    return context.set_id


def clear_contexts() -> None:
    """Clear cached contexts; intended for tests."""
    _contexts.clear()
