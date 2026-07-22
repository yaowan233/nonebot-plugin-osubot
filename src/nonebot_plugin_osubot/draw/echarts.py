import asyncio
import datetime
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from nonebot_plugin_htmlrender import template_to_pic

from ..api import get_users
from ..file import download_osu, map_path
from ..pp import cal_pp

template_path = str(Path(__file__).parent / "templates")

rank_color = {
    "X": "#ffc83a",
    "XH": "#c7eaf5",
    "S": "#ffc83a",
    "SH": "#c7eaf5",
    "A": "#84d61c",
    "B": "#e9b941",
    "C": "#fa8a59",
    "D": "#f55757",
}

rank_order = ["XH", "X", "SH", "S", "A", "B", "C", "D"]

# 影响星数的 mod（需要重新计算难度评级）
STAR_MODS = {"DT", "NC", "HT", "HR", "EZ", "DC", "DA"}


def build_history_data(
    pp_ls,
    date_ls,
    rank_ls,
    title: str,
    *,
    username: str | None = None,
    mode: str | None = None,
    user_id: int | str | None = None,
    source_label: str = "本地记录",
) -> dict[str, Any]:
    points = [
        (str(date), float(pp), int(rank))
        for pp, date, rank in zip(pp_ls, date_ls, rank_ls)
        if pp is not None and rank is not None and int(rank) > 0
    ]
    if not points:
        raise ValueError("没有可用于绘制历史趋势的数据")

    dates = [point[0] for point in points]
    pp_values = [point[1] for point in points]
    rank_values = [point[2] for point in points]
    try:
        parsed_dates = [datetime.date.fromisoformat(date) for date in dates]
    except ValueError:
        parsed_dates = []

    period_days = max((parsed_dates[-1] - parsed_dates[0]).days, 1) if parsed_dates else len(points)
    recent_index = 0
    if parsed_dates:
        cutoff = parsed_dates[-1] - datetime.timedelta(days=30)
        recent_index = next((index for index, date in enumerate(parsed_dates) if date >= cutoff), 0)

    start_rank = rank_values[0]
    rank_gain = start_rank - rank_values[-1]
    mode_labels = {
        "osu": "标准模式",
        "taiko": "太鼓模式",
        "fruits": "接水果模式",
        "mania": "键盘模式",
        "rxosu": "Relax 标准模式",
        "rxtaiko": "Relax 太鼓模式",
        "rxfruits": "Relax 接水果模式",
        "aposu": "Autopilot 标准模式",
    }
    display_name = username or title.split(" ", 1)[0] or "osu! 玩家"
    return {
        "username": display_name,
        "initial": display_name[:1].upper(),
        "user_id": str(user_id or ""),
        "avatar": f"https://a.ppy.sh/{user_id}" if user_id else "",
        "mode": mode_labels.get(mode or "", mode or "osu! 模式"),
        "period_days": period_days,
        "period": f"{dates[0]}—{dates[-1]}",
        "dates": dates,
        "pp_values": pp_values,
        "rank_values": rank_values,
        "start_pp": pp_values[0],
        "current_pp": pp_values[-1],
        "pp_gain": pp_values[-1] - pp_values[0],
        "recent_pp_gain": pp_values[-1] - pp_values[recent_index],
        "current_rank": rank_values[-1],
        "rank_gain": rank_gain,
        "rank_gain_rate": rank_gain / start_rank * 100 if start_rank else 0,
        "source_label": source_label,
    }


async def draw_history_plot(
    pp_ls,
    date_ls,
    rank_ls,
    title,
    *,
    username: str | None = None,
    mode: str | None = None,
    user_id: int | str | None = None,
    source_label: str = "本地记录",
) -> bytes:
    template_name = "pp_rank_line_chart.html"
    payload = build_history_data(
        pp_ls,
        date_ls,
        rank_ls,
        title,
        username=username,
        mode=mode,
        user_id=user_id,
        source_label=source_label,
    )
    payload_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    pic = await template_to_pic(
        template_path,
        template_name,
        {"payload_json": payload_json},
    )
    return pic


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _has_star_mod(score) -> bool:
    mods = getattr(score, "mods", None) or []
    return any(getattr(m, "acronym", str(m)) in STAR_MODS for m in mods)


async def _ensure_osu(set_id, map_id) -> Path | None:
    p = map_path / str(set_id) / f"{map_id}.osu"
    if p.exists():
        return p
    try:
        await download_osu(set_id, map_id)
        return p if p.exists() else None
    except Exception:
        return None


async def _calc_modded_stars(score, source: str) -> float | None:
    beatmap = getattr(score, "beatmap", None)
    if not beatmap:
        return None
    p = await _ensure_osu(getattr(beatmap, "set_id", None), getattr(beatmap, "id", None))
    if not p:
        return None
    try:
        res = cal_pp(score, str(p.absolute()), source)
        return _num(getattr(res, "stars", None))
    except Exception:
        return None


async def _resolve_stars(score_ls: list, source: str) -> list[float]:
    """返回每个 score 的星数；开了影响星数 mod 的会重新计算，失败则回退原值。"""

    async def one(idx, score):
        beatmap = getattr(score, "beatmap", None)
        base = _num(getattr(beatmap, "stars", 0)) if beatmap else 0.0
        if not beatmap or not _has_star_mod(score):
            return idx, base
        modded = await _calc_modded_stars(score, source)
        return idx, modded if modded and modded > 0 else base

    results = await asyncio.gather(*[one(i, s) for i, s in enumerate(score_ls)], return_exceptions=False)
    out = [0.0] * len(score_ls)
    for idx, val in results:
        out[idx] = round(val, 2)
    return out


async def build_bpa_data(score_ls: list, source: str) -> dict:
    """从已预处理的 score_ls 构建 bpa 图表所需的全部数据。"""
    pp_ls = [round(_num(i.pp), 0) for i in score_ls]

    # 并发解析 mod 后的真实星数
    stars_ls = await _resolve_stars(score_ls, source)

    length_ls: list[dict[str, Any]] = []
    for i in score_ls:
        color = rank_color.get(i.rank, "#9aa5ce")
        item_style: dict[str, Any] = {"color": color}
        if i.rank == "XH":
            item_style.update({"shadowBlur": 10, "shadowColor": "rgba(180,255,255,0.85)"})
        elif i.rank == "X":
            item_style.update({"shadowBlur": 10, "shadowColor": "rgba(255,255,0,0.85)"})
        length_ls.append(
            {
                "value": round(_num(getattr(getattr(i, "beatmap", None), "total_length", 0)), 1),
                "itemStyle": item_style,
            }
        )

    rank_data: dict[str, list[list[float]]] = {r: [] for r in rank_order}
    for idx, i in enumerate(score_ls):
        if not getattr(i, "beatmap", None):
            continue
        pp = _num(i.pp)
        rank_data.setdefault(i.rank, []).append([stars_ls[idx], round(pp, 1)])
    star_scatter = [{"name": r, "color": rank_color[r], "data": rank_data.get(r, [])} for r in rank_order]

    mods_pp: defaultdict[str, float] = defaultdict(float)
    for num, i in enumerate(score_ls):
        weighted = _num(i.pp) * 0.95**num
        mods = getattr(i, "mods", None) or []
        if not mods:
            mods_pp["NM"] += weighted
        for j in mods:
            mods_pp[getattr(j, "acronym", str(j))] += weighted
    mod_pp_data = [{"name": m, "value": round(pp, 2)} for m, pp in mods_pp.items()]
    mod_pp_data.sort(key=lambda x: x["value"], reverse=True)

    mapper_pp: defaultdict[Any, float] = defaultdict(float)
    for num, i in enumerate(score_ls):
        beatmap = getattr(i, "beatmap", None)
        if not beatmap:
            continue
        key = getattr(beatmap, "creator", None) if source == "ppysb" else getattr(beatmap, "user_id", None)
        mapper_pp[key] += _num(i.pp) * 0.95**num
    mapper_items = sorted(mapper_pp.items(), key=lambda x: x[1], reverse=True)[:9]
    if source == "ppysb":
        mapper_pp_data = [{"name": str(m), "value": round(pp, 2)} for m, pp in mapper_items]
    elif mapper_items:
        users = await get_users([m for m, _ in mapper_items])
        user_dic = {u.id: u.username for u in users}
        mapper_pp_data = [{"name": user_dic.get(m, str(m)), "value": round(pp, 2)} for m, pp in mapper_items]
    else:
        mapper_pp_data = []

    date_ls: list[str] = []
    for score in score_ls:
        ended_at = getattr(score, "ended_at", None)
        if isinstance(ended_at, (datetime.datetime, datetime.date)):
            date_value = ended_at.date() if isinstance(ended_at, datetime.datetime) else ended_at
            date_ls.append(date_value.isoformat())
        elif ended_at:
            date_ls.append(str(ended_at)[:10])

    bp_count = len(score_ls)
    weighted_pp = sum(_num(i.pp) * 0.95**num for num, i in enumerate(score_ls))
    total_pp = sum(_num(i.pp) for i in score_ls)
    accs = [round(_num(i.accuracy), 2) for i in score_ls if getattr(i, "accuracy", None) is not None]
    valid_stars = [s for s in stars_ls if s > 0]
    bpm_ls = [
        round(_num(getattr(i.beatmap, "bpm", 0)), 1)
        for i in score_ls
        if getattr(i, "beatmap", None) and _num(getattr(i.beatmap, "bpm", 0)) > 0
    ]
    avg_acc = sum(accs) / len(accs) if accs else 0.0
    avg_stars = sum(valid_stars) / len(valid_stars) if valid_stars else 0.0
    avg_bpm = sum(bpm_ls) / len(bpm_ls) if bpm_ls else 0.0
    top_mod = mod_pp_data[0]["name"] if mod_pp_data else "-"
    top_mapper = mapper_pp_data[0]["name"] if mapper_pp_data else "-"
    stats = {
        "weighted_pp": round(weighted_pp, 1),
        "total_pp": round(total_pp, 1),
        "bp_count": bp_count,
        "avg_acc": round(avg_acc, 2),
        "avg_stars": round(avg_stars, 2),
        "avg_bpm": round(avg_bpm, 1),
        "top_mod": top_mod,
        "top_mapper": top_mapper,
    }

    return {
        "pp_ls": pp_ls,
        "length_ls": length_ls,
        "star_scatter": star_scatter,
        "mod_pp_ls": mod_pp_data,
        "mapper_pp_ls": mapper_pp_data,
        "date_ls": date_ls,
        "acc_ls": accs,
        "bpm_ls": bpm_ls,
        "stats": stats,
    }


async def draw_bpa_plot(
    name,
    pp_ls,
    length_ls,
    star_scatter,
    mod_pp_ls,
    mapper_pp_ls,
    stats,
    date_ls=None,
    acc_ls=None,
    bpm_ls=None,
    *,
    username: str | None = None,
    mode: str | None = None,
    user_id: int | str | None = None,
    source: str = "osu",
    avatar_url: str | None = None,
) -> bytes:
    template_name = "bpa_chart.html"
    display_name = username or str(name).split(" ", 1)[0] or "osu! 玩家"
    mode_labels = {
        "osu": "标准模式",
        "taiko": "太鼓模式",
        "fruits": "接水果模式",
        "mania": "键盘模式",
        "rxosu": "Relax 标准模式",
        "rxtaiko": "Relax 太鼓模式",
        "rxfruits": "Relax 接水果模式",
        "aposu": "Autopilot 标准模式",
    }
    mode_icons = {
        "osu": "\ue800",
        "fruits": "\ue801",
        "mania": "\ue802",
        "taiko": "\ue803",
        "rxosu": "\ue800",
        "rxtaiko": "\ue803",
        "rxfruits": "\ue801",
        "aposu": "\ue800",
    }
    source_label = "ppy.sb" if source == "ppysb" else "osu! official"
    if avatar_url is None and user_id:
        avatar_host = "https://a.ppy.sb" if source == "ppysb" else "https://a.ppy.sh"
        avatar_url = f"{avatar_host}/{user_id}"
    pic = await template_to_pic(
        template_path,
        template_name,
        {
            "name": name,
            "username": display_name,
            "initial": display_name[:1].upper(),
            "mode_label": mode_labels.get(mode or "", mode or "osu! 模式"),
            "mode_icon": mode_icons.get(mode or "", "\ue800"),
            "user_id": str(user_id or ""),
            "avatar_url": avatar_url or "",
            "source_label": source_label,
            "pp_ls": pp_ls,
            "length_ls": length_ls,
            "star_scatter": star_scatter,
            "mod_pp_ls": mod_pp_ls,
            "mapper_pp_ls": mapper_pp_ls,
            "date_ls": date_ls or [],
            "acc_ls": acc_ls or [],
            "bpm_ls": bpm_ls or [],
            "stats": stats,
            "length": len(pp_ls),
        },
        pages={"viewport": {"width": 1620, "height": 10}},
    )
    return pic
