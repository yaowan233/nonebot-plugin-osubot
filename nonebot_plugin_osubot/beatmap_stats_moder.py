from typing import Optional

from .schema import Beatmap, NewScore
from .schema.score import Mod
from .utils import GM

OD0_MS = 80
OD10_MS = 20
AR0_MS = 1800
AR5_MS = 1200
AR10_MS = 450

OD_MS_STEP = (OD0_MS - OD10_MS) / 10
AR_MS_STEP1 = (AR0_MS - AR5_MS) / 5
AR_MS_STEP2 = (AR5_MS - AR10_MS) / 5


def modify_ar(base_ar, speed_mul, multiplier):
    ar = base_ar
    ar *= multiplier

    arms = AR0_MS - AR_MS_STEP1 * ar if ar < 5 else AR5_MS - AR_MS_STEP2 * (ar - 5)

    arms = min(AR0_MS, max(AR10_MS, arms))
    arms /= speed_mul

    ar = (
        (AR0_MS - arms) / AR_MS_STEP1
        if arms > AR5_MS
        else 5 + (AR5_MS - arms) / AR_MS_STEP2
    )
    return ar


def modify_od(base_od, speed_mul, multiplier):
    od = base_od
    od *= multiplier
    odms = OD0_MS - OD_MS_STEP * od
    odms = min(OD0_MS, max(OD10_MS, odms))
    odms /= speed_mul
    od = (OD0_MS - odms) / OD_MS_STEP
    return od


def with_mods(mapinfo: Beatmap, scoreinfo: Optional[NewScore], mods: list[Mod]):
    speed_mul = 1
    od_ar_hp_multiplier = 1
    mode = GM[scoreinfo.ruleset_id] if scoreinfo else mapinfo.mode
    for mod in mods:
        if mod.acronym == "DA":
            if mod.settings.circle_size is not None:
                mapinfo.cs = mod.settings.circle_size
            if mod.settings.approach_rate is not None:
                mapinfo.ar = mod.settings.approach_rate
            if mod.settings.drain_rate is not None:
                mapinfo.drain = mod.settings.drain_rate
            if mod.settings.overall_difficulty is not None:
                mapinfo.accuracy = mod.settings.overall_difficulty
        if mod.acronym == "DT" or mod.acronym == "NC":
            speed_mul = 1.5
            if mod.settings and mod.settings.speed_change:
                speed_mul = mod.settings.speed_change
            mapinfo.bpm *= speed_mul
            mapinfo.total_length /= speed_mul
        if mod.acronym == "HT":
            speed_mul = 0.75
            if mod.settings and mod.settings.speed_change:
                speed_mul = mod.settings.speed_change
            mapinfo.bpm *= speed_mul
            mapinfo.total_length /= speed_mul
        if mod.acronym == "HR" in mods:
            od_ar_hp_multiplier = 1.4
        if mod.acronym == "EZ" in mods:
            od_ar_hp_multiplier *= 0.5
    if mode == "mania":
        speed_mul = 1
    if mode not in ("mania", "taiko"):
        mapinfo.ar = modify_ar(mapinfo.ar, speed_mul, od_ar_hp_multiplier)
    if mode == "fruits":
        speed_mul = 1
    mapinfo.accuracy = modify_od(mapinfo.accuracy, speed_mul, od_ar_hp_multiplier)
    if mode not in ("mania", "taiko"):
        if Mod(acronym="HR") in mods:
            mapinfo.cs *= 1.3
        if Mod(acronym="EZ") in mods:
            mapinfo.cs *= 0.5
        mapinfo.cs = min(10.0, mapinfo.cs)
    mapinfo.drain *= od_ar_hp_multiplier
    mapinfo.drain = min(10.0, mapinfo.drain)
    return mapinfo
