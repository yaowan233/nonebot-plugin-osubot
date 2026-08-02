import math

from .schema.score import Mod, UnifiedScore

DEFAULT_SPEED_CHANGE = {"DT": 1.5, "NC": 1.5, "HT": 0.75}

mods_dic = {
    "CL": 0,
    "NO": 0,
    "NF": 1 << 0,
    "EZ": 1 << 1,
    "TD": 1 << 2,
    "HD": 1 << 3,
    "HR": 1 << 4,
    "SD": 1 << 5,
    "DT": 1 << 6,
    "RX": 1 << 7,
    "HT": 1 << 8,
    "NC": 1 << 9,
    "FL": 1 << 10,
    "AT": 1 << 11,
    "SO": 1 << 12,
    "RX2": 1 << 13,
    "PF": 1 << 14,
    "4K": 1 << 15,
    "5K": 1 << 16,
    "6K": 1 << 17,
    "7K": 1 << 18,
    "8K": 1 << 19,
    "FI": 1 << 20,
    "RD": 1 << 21,
    "Cinema": 1 << 22,
    "TG": 1 << 23,
    "9K": 1 << 24,
    "KC": 1 << 25,
    "1K": 1 << 26,
    "3K": 1 << 27,
    "2K": 1 << 28,
    "V2": 1 << 29,
    "MR": 1 << 30,
}


def get_mods(mods: int) -> list[Mod]:
    # Avoid copying the dictionary by iterating directly and filtering
    result = [Mod(acronym=mod) for mod, bit in mods_dic.items() if mod not in ("CL", "NO") and mods & bit]
    return result + [Mod(acronym="CL")]


def get_mods_list(score_ls: list[UnifiedScore], mods: list[str]) -> list[int]:
    if not mods:
        return list(range(len(score_ls)))
    # Optimize: create the set once instead of on every iteration
    mods_set = {mod.upper() for mod in mods}
    mods_index_ls = []
    for i, score in enumerate(score_ls):
        score_mods = {mod.acronym.upper() for mod in (score.mods or [])}
        matched = not (score_mods - {"CL"}) if mods_set == {"NM"} else mods_set.issubset(score_mods)
        if matched:
            mods_index_ls.append(i)
    return mods_index_ls


def calc_mods(mods: list[Mod]) -> int:
    num = 0
    for mod in mods:
        num ^= mods_dic.get(mod.acronym, 0)
    return num


def get_speed_change_label(mod: Mod) -> str | None:
    """Return a compact label only for a non-default speed-changing mod."""
    default = DEFAULT_SPEED_CHANGE.get(mod.acronym)
    if default is None or not mod.settings:
        return None
    value = mod.settings.get("speed_change")
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(rate) or rate <= 0 or math.isclose(rate, default, abs_tol=1e-6):
        return None
    return f"{rate:.2f}×"


def get_speed_change_labels(mods: list[Mod]) -> dict[str, str]:
    """Collect visible speed labels, preserving DT settings when NC replaces DT."""
    labels = {mod.acronym: label for mod in mods if (label := get_speed_change_label(mod))}
    acronyms = {mod.acronym for mod in mods}
    if "NC" in acronyms and "NC" not in labels and "DT" in labels:
        labels["NC"] = labels["DT"]
    return labels
