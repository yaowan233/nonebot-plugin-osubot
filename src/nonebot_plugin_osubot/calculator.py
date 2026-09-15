"""Project adapter for the osu-tools decoder and official ruleset calculators."""

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from osu_tools import OsuCalculator


@dataclass(frozen=True)
class MapAttributes:
    mode: int
    cs: float
    ar: float
    od: float
    hp: float
    bpm: float
    n_objects: int
    n_circles: int
    n_sliders: int
    n_spinners: int
    n_holds: int


class CachedOsuCalculator(OsuCalculator):
    """Keep .NET objects serialized and include mod settings in cache identities."""

    def __init__(self):
        self._calculation_lock = threading.RLock()
        super().__init__(prepared_cache_size=128, max_workers=1)

    def calculate_many(self, requests):
        with self._calculation_lock:
            results = super().calculate_many(requests)
            for result in results:
                if not result.is_success:
                    raise ValueError(result.error)
            return results

    def _mods_cache_key(self, mods):
        return tuple(
            json.dumps(
                {
                    "acronym": self._get_mod_acronym(mod),
                    "settings": (mod.get("settings") if isinstance(mod, dict) else getattr(mod, "settings", None)),
                },
                sort_keys=True,
            )
            for mod in (mods or [])
        )

    def _parse_mods(self, mod_list, ruleset):
        parsed = super()._parse_mods(mod_list, ruleset)
        for source in mod_list or []:
            settings = source.get("settings") if isinstance(source, dict) else getattr(source, "settings", None)
            if not settings:
                continue
            acronym = self._get_mod_acronym(source)
            target = next((m for m in parsed if str(m.Acronym).upper() == acronym.upper()), None)
            if target is None:
                raise ValueError(f"不支持 Mod 参数：{acronym}")
            for name, value in settings.items():
                if value is None:
                    continue
                prop = "".join(part.title() for part in name.split("_"))
                bindable = getattr(target, prop, None)
                if bindable is None or not hasattr(bindable, "Value"):
                    raise ValueError(f"不支持 Mod 参数：{acronym}.{name}")
                bindable.Value = value
        return parsed

    def _calculate_prepared(self, **kwargs):
        result = super()._calculate_prepared(**kwargs)
        result.pp_difficulty = 0.0
        if kwargs["mode"] not in {1, 3}:
            return result
        # The public result omits mania/taiko's Difficulty component. Obtain it
        # from the same official calculator and the already generated statistics.
        score = self.ScoreInfo()
        score.Ruleset = kwargs["ruleset"].RulesetInfo
        score.BeatmapInfo = kwargs["working_beatmap"].BeatmapInfo
        score.Mods = kwargs["csharp_mods"].ToArray()
        score.Accuracy = kwargs["acc"] / 100
        score.MaxCombo = kwargs["combo"] if kwargs["combo"] is not None else result.max_combo
        score.LegacyTotalScore = kwargs["legacy_total_score"] or 0
        for name, count in result.stats_used.items():
            if count > 0:
                score.Statistics[getattr(self.HitResult, name)] = count
        attributes = kwargs["ruleset"].CreatePerformanceCalculator().Calculate(score, kwargs["diff_attr"])
        result.pp_difficulty = float(getattr(attributes, "Difficulty", 0.0))
        return result

    def map_attributes(self, path, mode, mods=()):
        with self._calculation_lock:
            ruleset = self.rulesets[mode]
            beatmap, working, _ = self._load_working_beatmap(str(Path(path).resolve()), ruleset)
            playable = working.GetPlayableBeatmap(ruleset.RulesetInfo, self._parse_mods(list(mods), ruleset))
            names = [str(obj.GetType().Name) for obj in playable.HitObjects]
            holds = names.count("HoldNote")
            circles = sum(name in {"HitCircle", "Hit", "Fruit", "Note"} for name in names)
            sliders = sum(name in {"Slider", "DrumRoll", "JuiceStream"} for name in names)
            difficulty = beatmap.Difficulty
            return MapAttributes(
                mode,
                float(difficulty.CircleSize),
                float(difficulty.ApproachRate),
                float(difficulty.OverallDifficulty),
                float(difficulty.DrainRate),
                60000.0 / beatmap.GetMostCommonBeatLength(),
                len(names),
                circles,
                sliders,
                len(names) - circles - sliders - holds,
                holds,
            )

    def stars(self, path, mode, mods):
        with self._calculation_lock:
            ruleset = self.rulesets[mode]
            _, working, _ = self._load_working_beatmap(str(Path(path).resolve()), ruleset)
            return float(
                ruleset.CreateDifficultyCalculator(working).Calculate(self._parse_mods(mods, ruleset)).StarRating
            )
