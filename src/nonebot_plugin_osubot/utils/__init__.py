import re

from ..server import ModeVariant, PlayMode

_LEGACY_MODE_IDS = (0, 1, 2, 3, 4, 5, 6, 8)
GM = {mode_id: PlayMode.parse(mode_id).ruleset.name.lower() for mode_id in _LEGACY_MODE_IDS}
GM[2] = GM[6] = "fruits"
NGM = {str(mode_id): PlayMode.parse(mode_id).key for mode_id in _LEGACY_MODE_IDS}
GMN = {
    "osu": "Std",
    "taiko": "Taiko",
    "fruits": "Ctb",
    "mania": "Mania",
    "rxosu": "RX Std",
    "rxtaiko": "RX Taiko",
    "rxfruits": "RX Ctb",
    "aposu": "AP Std",
}
FGM = {mode_name: int(mode_id) for mode_id, mode_name in NGM.items()}


def parse_mode(value: int | str, allow_special: bool = False) -> str | None:
    mode = PlayMode.parse(value)
    if mode is None or not allow_special and mode.variant != ModeVariant.STANDARD:
        return None
    return mode.legacy_key


BEATMAPSET_URL_PATTERN = re.compile(r"(?:https?://)?osu\.ppy\.sh/beatmapsets/(\d+)(?:#[^/\s]+/(\d+))?")
BEATMAP_URL_PATTERN = re.compile(r"(?:https?://)?osu\.ppy\.sh/(?:b|beatmaps)/(\d+)")
USER_URL_PATTERN = re.compile(r"(?:https?://)?osu\.ppy\.sh/(?:u|users)/(\d+)")


def extract_beatmap_id(value: str) -> str | None:
    if match := BEATMAPSET_URL_PATTERN.search(value):
        return match.group(2)
    if match := BEATMAP_URL_PATTERN.search(value):
        return match.group(1)
    return None


def extract_beatmapset_id(value: str) -> str | None:
    if match := BEATMAPSET_URL_PATTERN.search(value):
        return match.group(1)
    return None


def extract_user_id(value: str) -> str | None:
    if match := USER_URL_PATTERN.search(value):
        return match.group(1)
    return None


def normalize_map_mode(requested_mode: int | str, native_mode: int, source: str = "osu") -> str:
    """Return a score mode compatible with the beatmap's native ruleset."""
    del source  # Compatibility parameter; server mode support is validated at the GameServer seam.
    requested = PlayMode.parse(requested_mode)
    if requested is None:
        raise ValueError(f"不支持的模式: {requested_mode}")
    return requested.for_native_ruleset(native_mode).legacy_key


def mods2list(args: str) -> list:
    args = args.replace(" ", "").replace(",", "").replace("，", "")
    args = args.upper()
    return [args[i : i + 2] for i in range(0, len(args), 2)]
