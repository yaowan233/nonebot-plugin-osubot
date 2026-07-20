import re


GM = {
    0: "osu",
    1: "taiko",
    2: "fruits",
    3: "mania",
    4: "osu",
    5: "taiko",
    6: "fruits",
    8: "osu",
}
NGM = {
    "0": "osu",
    "1": "taiko",
    "2": "fruits",
    "3": "mania",
    "4": "rxosu",
    "5": "rxtaiko",
    "6": "rxfruits",
    "8": "aposu",
}
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
FGM = {
    "osu": 0,
    "taiko": 1,
    "fruits": 2,
    "mania": 3,
    "rxosu": 4,
    "rxtaiko": 5,
    "rxfruits": 6,
    "aposu": 8,
}

MODE_ALIASES = {
    "0": "0",
    "osu": "0",
    "osu!": "0",
    "o": "0",
    "std": "0",
    "standard": "0",
    "1": "1",
    "taiko": "1",
    "t": "1",
    "tk": "1",
    "2": "2",
    "catch": "2",
    "c": "2",
    "ctb": "2",
    "fruits": "2",
    "3": "3",
    "mania": "3",
    "m": "3",
    "4": "4",
    "rx": "4",
    "rxstd": "4",
    "rxosu": "4",
    "5": "5",
    "rxtaiko": "5",
    "rxtk": "5",
    "6": "6",
    "rxcatch": "6",
    "rxctb": "6",
    "rxfruits": "6",
    "8": "8",
    "ap": "8",
    "apstd": "8",
    "aposu": "8",
}


def parse_mode(value: int | str, allow_special: bool = False) -> str | None:
    mode = MODE_ALIASES.get(str(value).strip().lower())
    if mode is None or not allow_special and mode not in {"0", "1", "2", "3"}:
        return None
    return mode


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
    requested = int(requested_mode)
    if native_mode == 0:
        # Standard beatmaps may be converted to other rulesets.
        return str(requested)
    if source != "ppysb":
        return str(native_mode)
    if requested in {4, 5, 6}:
        # Preserve the RX category while selecting the map's actual ruleset.
        return str({1: 5, 2: 6}.get(native_mode, native_mode))
    # AP only exists for standard; mania has no RX/AP category either.
    return str(native_mode)


def mods2list(args: str) -> list:
    args = args.replace(" ", "").replace(",", "").replace("，", "")
    args = args.upper()
    return [args[i : i + 2] for i in range(0, len(args), 2)]
