def personal_request(uid, mode, target, candidate_limit, result_limit, filters=None):
    from .recommendation_filters import RecommendationFilters

    body = {
        "player_id": int(uid),
        "mode": mode,
        "target": "balanced" if target == "mixed" else target,
        "candidate_limit": candidate_limit,
        "result_limit": result_limit,
        "min_stars": 0,
        "max_stars": 20,
        "max_length": 3600,
        "mods": ["NM", "DT", "HT", "HD", "HR", "HDDT", "HDHR"],
        "exclude_recorded_plays": True,
        "include_converts": mode in {"taiko", "fruits"},
    }
    if filters is not None:
        parsed = RecommendationFilters.model_validate(filters)
        body.update(parsed.for_mode(mode))
    for name, default_max in (("stars", 20), ("bpm", 1000), ("length", 3600)):
        if body.get("min_" + name, 0) > body.get("max_" + name, default_max):
            raise ValueError(f"{name} 下限不能超过上限")
    return body


def prediction_display(item, mode):
    goal = item.get("practice_target") if mode == "fruits" else item.get("accuracy_target")
    evidence = item.get("fc_evidence") if mode == "fruits" else item.get("accuracy_evidence")
    line = ""
    if goal:
        if mode == "mania":
            line = f"{item['key_count']}K · ACC 目标" if item.get("key_count") else "ACC 目标"
        else:
            misses = goal.get("misses")
            line = "FC 目标" if misses == 0 else f"{misses} Miss 目标" if misses is not None else "ACC 目标"
            combo = goal.get("combo")
            if combo is not None:
                line += f" · {int(combo)}x"
        references = (evidence or {}).get("references", [])
        if references:
            line += f" · {len(references)}人实绩"
        return {
            "pred_pp": goal["pp"],
            "pred_acc": goal["accuracy"],
            "weighted_gain": goal.get("weighted_gain"),
            "evidence_line": line,
        }
    if mode in {"osu", "fruits"}:
        miss = item.get("expected_miss")
        if miss is None:
            miss = item.get("pred_miss")
        combo = item.get("pred_combo")
        source = "模型预测" if item.get("performance_prediction_source") == "osu-joint-model" else "预测"
        parts = [source]
        if miss is not None:
            parts.append(f"{miss:.1f} Miss")
        if combo is not None:
            parts.append(f"{int(combo)}x")
        if miss is None and combo is None:
            parts.append("无练习目标")
        line = " · ".join(parts)
    else:
        prefix = f"{item['key_count']}K · " if mode == "mania" and item.get("key_count") else ""
        line = prefix + "预测 ACC · 无练习目标"
    return {
        "pred_pp": item.get("pred_pp", 0),
        "pred_acc": item.get("pred_acc", 0),
        "weighted_gain": item.get("predicted_weighted_snapshot_gain"),
        "evidence_line": line,
    }
