import asyncio
from io import BytesIO
from typing import Union, Optional
from datetime import datetime, timedelta

from PIL import ImageDraw, UnidentifiedImageError

from ..pp import cal_pp
from ..mods import get_mods_list
from ..api import get_user_scores, get_user_info_data
from ..exceptions import NetworkError
from ..schema.score import Mod, UnifiedScore
from .score import cal_legacy_acc, cal_legacy_rank
from ..file import map_path, get_pfm_img, download_osu
from .utils import draw_fillet, draw_fillet2, open_user_icon, filter_scores_with_regex
from .static import BgImg, Image, BgImg1, ModsDict, RankDict, Torus_Regular_20, Torus_Regular_25, Torus_SemiBold_25


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
    if not is_lazer:
        scores = [i for i in scores if any(mod.acronym == "CL" for mod in i.mods)]
    if mods:
        mods_ls = get_mods_list(scores, mods)
        if low_bound > len(mods_ls):
            raise NetworkError(f'未找到开启 {"|".join(mods)} Mods的成绩')
        if high_bound > len(mods_ls):
            mods_ls = mods_ls[low_bound - 1 :]
        else:
            mods_ls = mods_ls[low_bound - 1 : high_bound]
        score_ls_filtered = [scores[i] for i in mods_ls]
    else:
        score_ls_filtered = scores[low_bound - 1 : high_bound]
    if project == "tbp":
        score_ls_filtered = [score for score in scores if score.ended_at > datetime.now() - timedelta(days=day + 1)]
        if not score_ls_filtered:
            raise NetworkError("未查询到游玩记录")
    for score_info in score_ls_filtered:
        # 判断是否开启lazer模式
        if is_lazer:
            score_info.legacy_total_score = score_info.total_score
        if not is_lazer and Mod(acronym="CL") in score_info.mods:
            score_info.mods.remove(Mod(acronym="CL"))
        if score_info.ruleset_id == 3 and not is_lazer:
            score_info.accuracy = cal_legacy_acc(score_info.statistics)
        if not is_lazer:
            is_hidden = any(i in score_info.mods for i in (Mod(acronym="HD"), Mod(acronym="FL"), Mod(acronym="FI")))
            score_info.rank = cal_legacy_rank(score_info, is_hidden)
    if search_condition:
        score_ls_filtered = filter_scores_with_regex(score_ls_filtered, search_condition)
    if not score_ls_filtered:
        raise NetworkError("未查询到游玩记录")
    msg = await draw_pfm(project, uid, scores, score_ls_filtered, mode, source, low_bound, high_bound, day, is_lazer)
    return msg


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
    is_lazer: bool = True,
) -> Union[str, BytesIO]:
    task0 = [
        get_pfm_img(
            f"https://assets.ppy.sh/beatmaps/{i.beatmap.set_id}/covers/list.jpg",
            map_path / f"{i.beatmap.set_id}" / "list.jpg",
        )
        for i in score_ls_filtered
    ]

    task1 = [
        get_pfm_img(
            f"https://assets.ppy.sh/beatmaps/{i.beatmap.set_id}/covers/cover.jpg",
            map_path / f"{i.beatmap.set_id}" / "cover.jpg",
        )
        for i in score_ls_filtered
    ]
    task2 = [
        download_osu(i.beatmap.set_id, i.beatmap.id)
        for i in score_ls_filtered
        if not (map_path / f"{i.beatmap.set_id}" / f"{i.beatmap.id}.osu").exists()
    ]
    info = await get_user_info_data(uid, mode, source)
    bg_ls = await asyncio.gather(*task0)
    large_banner_ls = await asyncio.gather(*task1)
    await asyncio.gather(*task2)
    bplist_len = len(score_ls_filtered)
    im = Image.new("RGBA", (1420, 280 + 177 * ((bplist_len + 1) // 2 - 1)), (31, 41, 46, 255))
    if project in ("prlist", "relist"):
        im.alpha_composite(BgImg1)
    else:
        im.alpha_composite(BgImg)
    draw = ImageDraw.Draw(im)
    f_div = Image.new("RGBA", (1450, 2), (255, 255, 255, 255)).convert("RGBA")
    im.alpha_composite(f_div, (0, 100))
    if project == "bp":
        uinfo = f"{mode.capitalize()} 模式 | BP {low_bound} - {high_bound}"
    elif project == "prlist":
        uinfo = f"{mode.capitalize()} 模式 | 近24h内上传成绩"
    elif project == "relist":
        uinfo = f"{mode.capitalize()} 模式 | 近24h内（含死亡）上传成绩"
    else:
        uinfo = f"{mode.capitalize()} 模式 | 近{day + 1}日新增 BP"
    draw.text((1388, 80), uinfo, font=Torus_SemiBold_25, anchor="rm")
    for num, bp in enumerate(score_ls_filtered):
        h_num = 177 * (num // 2)  # 每两个数据换行
        offset = 695 * (num % 2)  # 数据在右边时的偏移量

        # BP排名
        index = score_ls.index(bp)
        draw.text(
            (40 + offset, 190 + h_num),
            str(index + 1),
            font=Torus_Regular_20,
            anchor="rm",
        )

        # 获取谱面大banner
        try:
            banner = Image.open(large_banner_ls[num]).convert("RGBA").resize((650, 150))
            banner_with_fillet = draw_fillet2(banner, 15)
            im.alpha_composite(banner_with_fillet, (45 + offset, 114 + h_num))
        except UnidentifiedImageError:
            ...

        # 获取谱面banner
        try:
            bg = Image.open(bg_ls[num]).convert("RGBA").resize((150, 150))
            bg_imag = draw_fillet(bg, 15)
            im.alpha_composite(bg_imag, (45 + offset, 114 + h_num))
        except UnidentifiedImageError:
            ...

        # 地区排名和地区
        draw.text(
            (115, 70),
            f"{info.country_code} #{info.statistics.country_rank}",
            font=Torus_SemiBold_25,
            anchor="lm",
        )

        # 用户名
        draw.text(
            (115, 25),
            f"{info.username}",
            font=Torus_SemiBold_25,
            anchor="lm",
        )

        # 头像
        user_icon = await open_user_icon(info, source)
        icon_bg = user_icon.convert("RGBA").resize((75, 75))
        icon_img = draw_fillet(icon_bg, 15)
        im.alpha_composite(icon_img, (30, 10))
        user_icon.close()

        # mods
        if bp.mods:
            for mods_num, s_mods in enumerate(bp.mods):
                if s_mods.acronym in ModsDict:
                    mods_img = ModsDict[s_mods.acronym].convert("RGBA")
                    im.alpha_composite(mods_img, (210 + offset + 50 * mods_num, 192 + h_num))
            if (bp.rank == "X" or bp.rank == "S") and (
                Mod(acronym="HD") in bp.mods or Mod(acronym="FL") in bp.mods or Mod(acronym="FI") in bp.mods
            ):
                bp.rank += "H"

        # 曲名&作曲
        metadata = f"{bp.beatmap.title} | by {bp.beatmap.artist}"
        if len(metadata) > 30:
            metadata = metadata[:27] + "..."
        draw.text((210 + offset, 135 + h_num), metadata, font=Torus_Regular_25, anchor="lm")

        # 地图版本&时间
        difficulty = bp.beatmap.version
        if len(difficulty) > 30:
            difficulty = difficulty[:27] + "..."
        osu = map_path / f"{bp.beatmap.set_id}" / f"{bp.beatmap.id}.osu"
        pp_info = cal_pp(bp, str(osu.absolute()), is_lazer)
        difficulty = f"{pp_info.difficulty.stars:.2f}★ | {difficulty}"
        draw.text(
            (210 + offset, 168 + h_num),
            difficulty,
            font=Torus_Regular_20,
            anchor="lm",
            fill=(238, 171, 0, 255),
        )

        # 达成时间
        draw.text(
            (210 + offset, 245 + h_num),
            f"{bp.ended_at.strftime('%Y-%m-%dT%H:%M:%S')}",
            font=Torus_Regular_20,
            anchor="lm",
        )

        # acc
        draw.text(
            (680 + offset, 210 + h_num),
            f"{bp.accuracy:.2f}%",
            font=Torus_SemiBold_25,
            anchor="rm",
            fill=(238, 171, 0, 255),
        )

        # rank
        rank_bg = RankDict[f"ranking-{bp.rank}"].resize((60, 30))
        im.alpha_composite(rank_bg, (621 + offset, 120 + h_num))

        # mapid
        draw.text(
            (680 + offset, 245 + h_num),
            f"ID: {bp.beatmap.id}",
            font=Torus_Regular_20,
            anchor="rm",
        )

        # pp
        draw.text(
            (645 + offset, 174 + h_num),
            f"{pp_info.pp:.0f}",
            font=Torus_SemiBold_25,
            anchor="rm",
            fill=(255, 102, 171, 255),
        )
        draw.text(
            (648 + offset, 170 + h_num),
            "pp",
            font=Torus_SemiBold_25,
            anchor="lm",
            fill=(209, 148, 176, 255),
        )

        # 分割线
        div = Image.new("RGBA", (1400, 2), (46, 53, 56, 255)).convert("RGBA")
        im.alpha_composite(div, (25, 275 + h_num))

        await asyncio.sleep(0)
    image_bytesio = BytesIO()
    im = im.convert("RGB")
    im.save(image_bytesio, "JPEG", quality=40)
    return image_bytesio
