import asyncio
import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import jinja2
from nonebot_plugin_htmlrender import get_new_page

from ..api import get_user_info_data, get_user_scores
from ..exceptions import NetworkError
from ..file import download_osu, get_pfm_img, map_path
from ..mods import get_mods_list
from ..pp import cal_pp
from ..schema.score import UnifiedScore
from .score import cal_score_info
from .utils import filter_scores_with_regex


async def draw_bp(
    project: str,
    uid: int,
    is_lazer: bool,
    mode: str,
    mods: Optional[list],
    low_bound: int,
    high_bound: int,
    day: int,
    search_condition: list,
    source: str,
) -> BytesIO:
    scores = await get_user_scores(uid, mode, "best", source=source, legacy_only=not is_lazer)
    if mods:
        mods_ls = get_mods_list(scores, mods)
        if low_bound > len(mods_ls):
            raise NetworkError(f"未找到开启 {'|'.join(mods)} Mods的成绩")
        selected = [scores[i] for i in mods_ls[low_bound - 1 : high_bound]]
    else:
        selected = scores[low_bound - 1 : high_bound]
    if project == "tbp":
        selected = [score for score in scores if score.ended_at > datetime.now() - timedelta(days=day + 1)]
        if not selected:
            raise NetworkError("未查询到游玩记录")
    for index, score in enumerate(selected):
        if score.mods and any(mod.acronym == "NC" for mod in score.mods):
            score.mods = [mod for mod in score.mods if mod.acronym != "DT"]
        selected[index] = cal_score_info(is_lazer, score, source)
    if search_condition:
        selected = filter_scores_with_regex(selected, search_condition)
    if not selected:
        raise NetworkError("未查询到游玩记录")
    return await draw_pfm(project, uid, scores, selected, mode, source, low_bound, high_bound, day)


async def draw_pfm(
    project: str,
    uid: int,
    score_ls: list[UnifiedScore],
    score_ls_filtered: list[UnifiedScore],
    mode: str,
    source: str,
    low_bound: int = 0,
    high_bound: int = 0,
    day: int = 0,
) -> Union[str, BytesIO]:
    cover_paths = [map_path / str(score.beatmap.set_id) / "cover.jpg" for score in score_ls_filtered]
    cover_tasks = [
        get_pfm_img(
            f"https://assets.ppy.sh/beatmaps/{score.beatmap.set_id}/covers/cover.jpg",
            cover_path,
        )
        for score, cover_path in zip(score_ls_filtered, cover_paths)
    ]
    osu_tasks = [
        download_osu(score.beatmap.set_id, score.beatmap.id)
        for score in score_ls_filtered
        if not (map_path / str(score.beatmap.set_id) / f"{score.beatmap.id}.osu").exists()
    ]
    info, *_ = await asyncio.gather(
        get_user_info_data(uid, mode, source),
        asyncio.gather(*cover_tasks),
        asyncio.gather(*osu_tasks),
    )

    plays = []
    for score, cover_path in zip(score_ls_filtered, cover_paths):
        osu_file = map_path / str(score.beatmap.set_id) / f"{score.beatmap.id}.osu"
        stars = score.beatmap.stars
        pp_value = score.pp or 0
        if osu_file.exists():
            try:
                pp_info = cal_pp(score, str(osu_file.absolute()), source)
                stars = pp_info.stars
                if source != "ppysb":
                    pp_value = pp_info.pp
            except Exception:
                pass
        mods = [mod.acronym for mod in score.mods]
        if "NC" in mods and "DT" in mods:
            mods.remove("DT")
        try:
            bp_index = score_ls.index(score) + 1
        except ValueError:
            bp_index = low_bound + len(plays)
        plays.append(
            {
                "index": bp_index,
                "title": score.beatmap.title,
                "artist": score.beatmap.artist,
                "version": score.beatmap.version,
                "cover": cover_path.resolve().as_uri()
                if cover_path.exists()
                else f"https://assets.ppy.sh/beatmaps/{score.beatmap.set_id}/covers/cover.jpg",
                "pp": pp_value,
                "accuracy": score.accuracy,
                "stars": stars,
                "mods": mods,
                "date": score.ended_at.strftime("%Y.%m.%d"),
            }
        )

    if project == "bp":
        shown_high = min(high_bound, low_bound + len(score_ls_filtered) - 1)
        section_title = "最佳成绩"
        range_label = f"BP {low_bound}–{shown_high}"
    elif project == "prlist":
        section_title, range_label = "上传成绩", "近 24 小时"
    elif project == "relist":
        section_title, range_label = "上传成绩", "近 24 小时 · 含未通过"
    else:
        section_title, range_label = "新增最佳成绩", f"近 {day + 1} 日"
    payload = {
        "mode": mode,
        "section_title": section_title,
        "range_label": range_label,
        "generated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "user": {
            "id": info.id,
            "name": info.username,
            "avatar": info.avatar_url,
            "country": info.country_code,
            "support_level": info.support_level,
            "team": info.team.model_dump() if info.team else None,
            "statistics": info.statistics.model_dump() if info.statistics else {},
        },
        "plays": plays,
    }

    template_path = Path(__file__).parent / "bp_templates"
    template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(str(template_path)), enable_async=True
    ).get_template("index.html")
    async with get_new_page(1) as page:
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.goto((template_path / "index.html").as_uri(), wait_until="load")
        await page.set_content(
            await template.render_async(payload_json=json.dumps(payload, ensure_ascii=False)),
            wait_until="domcontentloaded",
        )
        await page.evaluate(
            "Promise.race([Promise.all([document.fonts.ready,"
            "...Array.from(document.images,x=>x.decode().catch(()=>{}))]),"
            "new Promise(resolve=>setTimeout(resolve,8000))])"
        )
        await page.evaluate(
            "const box=document.querySelector('.minor'),label=box?.querySelector('span');"
            "if(box&&label&&!box.querySelector('.minor-lines')){"
            "const parts=label.textContent.split(' · '),logo=box.querySelector('img')?.outerHTML||'';"
            "const cut=Math.max(1,parts.length-2);"
            "box.innerHTML=logo+'<span class=\"minor-lines\"><span>'+"
            "parts.slice(0,cut).join(' · ')+'</span><span>'+"
            "parts.slice(cut).join(' · ')+'</span></span>'}"
        )
        element = await page.query_selector("#display")
        assert element
        result = await element.screenshot(type="jpeg", quality=90)
    return BytesIO(result)
