from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FEATURE_LIMITS = {
    "osu": {
        "slider_ratio": 1,
        "jump_p90": 1000,
        "angle_change_ratio": 1,
        "object_density_avg": 1000,
        "object_density_peak_1000": 10000,
    },
    "taiko": {
        "rim_ratio": 1,
        "big_ratio": 1,
        "color_change_ratio": 1,
        "object_density_avg": 1000,
        "object_density_peak_1000": 10000,
    },
    "fruits": {
        "direction_change_ratio": 1,
        "edge_ratio": 1,
        "x_jump_p90": 512,
        "object_density_avg": 1000,
        "object_density_peak_1000": 10000,
    },
    "mania": {
        "ln_ratio": 1,
        "chord_ratio": 1,
        "ln_overlap_ratio": 1,
        "note_density_avg": 1000,
        "note_density_peak_1000": 10000,
    },
}


class RecommendationFeatureRange(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.min is None and self.max is None:
            raise ValueError("特征范围至少需要 min 或 max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("特征范围下限不能超过上限")
        return self


class RecommendationFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    min_stars: float | None = Field(default=None, ge=0, le=20, description="最低星数")
    max_stars: float | None = Field(default=None, ge=0, le=20, description="最高星数")
    min_bpm: float | None = Field(default=None, ge=0, le=1000, description="应用 Mods 后的最低 BPM")
    max_bpm: float | None = Field(default=None, ge=0, le=1000, description="应用 Mods 后的最高 BPM")
    min_length: float | None = Field(default=None, ge=0, le=3600, description="最短时长，秒，应用 Mods 后")
    max_length: float | None = Field(default=None, ge=1, le=3600, description="最长时长，秒，应用 Mods 后")
    mods: list[Literal["NM", "HD", "HR", "DT", "HT", "HDDT", "HDHR", "DTHR", "HDHRDT"]] | None = Field(
        default=None, min_length=1, max_length=9, description="允许的完整 Mod 组合；只要无 Mod 填 NM"
    )
    key_counts: list[Annotated[int, Field(strict=True, ge=4, le=10)]] | None = Field(
        default=None, min_length=1, max_length=7, description="仅 Mania：多选 4K 到 10K，不填则不限"
    )
    include_converts: bool | None = Field(default=None, description="是否包含转谱；CTB 和太鼓默认包含，其他默认排除")
    exclude_recorded_plays: bool | None = Field(default=None, description="默认排除已记录成绩；允许重刷时设 false")
    result_limit: int | None = Field(default=None, strict=True, ge=1, le=50, description="返回谱面数，1 到 50")
    feature_ranges: dict[str, RecommendationFeatureRange] | None = Field(
        default=None,
        description="模式特征范围 {特征名: {min,max}}；ratio 均用 0..1，例如 30% 填 0.3。"
        "mania: ln_ratio/chord_ratio/ln_overlap_ratio/note_density_avg/note_density_peak_1000；"
        "osu: slider_ratio/jump_p90/angle_change_ratio/object_density_avg/object_density_peak_1000；"
        "fruits: direction_change_ratio/edge_ratio/x_jump_p90/object_density_avg/object_density_peak_1000；"
        "taiko: rim_ratio/big_ratio/color_change_ratio/object_density_avg/object_density_peak_1000。"
        "density 为每秒物件数；jump 为坐标距离，不是星数。",
    )

    def for_mode(self, mode):
        values = self.model_dump(exclude_none=True)
        if self.key_counts is not None and mode != "mania":
            raise ValueError("键数筛选只能用于 Mania")
        for name in ("mods", "key_counts"):
            items = values.get(name, [])
            if len(items) != len(set(items)):
                raise ValueError(f"{name} 不允许重复")
        if mode != "taiko" and any(mod in {"DTHR", "HDHRDT"} for mod in (self.mods or [])):
            raise ValueError("DTHR 和 HDHRDT 仅支持太鼓")
        for name, bounds in (self.feature_ranges or {}).items():
            maximum = FEATURE_LIMITS[mode].get(name)
            if maximum is None:
                raise ValueError(f"{mode} 不支持特征 {name}")
            if any(value is not None and value > maximum for value in (bounds.min, bounds.max)):
                raise ValueError(f"{name} 上限为 {maximum}；比例请用 0 到 1")
        return values
