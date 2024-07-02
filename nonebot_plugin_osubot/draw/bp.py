import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from time import strptime, mktime
from typing import Union, Optional

from PIL import ImageDraw, UnidentifiedImageError

from .score import cal_legacy_acc, cal_legacy_rank
from .static import (
    BgImg,
    BgImg1,
    Torus_Regular_25,
    Torus_Regular_20,
    Torus_SemiBold_25,
    Image,
    osufile,
)
from .utils import draw_fillet, draw_fillet2
from ..api import osu_api
from ..database import UserData
from ..file import get_projectimg
from ..mods import get_mods_list
from ..schema import NewScore
from ..schema.score import Mod
from ..utils import GMN


async def draw_bp(
    project: str,
    uid: int,
    user_id: int,
    mode: str,
    mods: Optional[list],
    low_bound: int = 0,
    high_bound: int = 0,
    day: int = 0,
    is_name: bool = False,
) -> Union[str, BytesIO]:
    player = await UserData.get_or_none(user_id=user_id)
    lazer_mode = True if not player else player.lazer_mode
    bp_info = await osu_api(
        "bp", uid, mode, is_name=is_name, legacy_only=int(not lazer_mode)
    )
    if isinstance(bp_info, str):
        return bp_info
    score_ls = [NewScore(**i) for i in bp_info]
    if not lazer_mode:
        score_ls = [i for i in score_ls if any(mod.acronym == "CL" for mod in i.mods)]
    if not bp_info:
        return f"未查询到在 {GMN[mode]} 的游玩记录"
    user = bp_info[0]["user"]["username"]
    if project == "bp":
        if mods:
            mods_ls = get_mods_list(score_ls, mods)
            if low_bound > len(mods_ls):
                return f'未找到开启 {"|".join(mods)} Mods的成绩'
            if high_bound > len(mods_ls):
                mods_ls = mods_ls[low_bound - 1 :]
            else:
                mods_ls = mods_ls[low_bound - 1 : high_bound]
            score_ls_filtered = [score_ls[i] for i in mods_ls]
        else:
            score_ls_filtered = score_ls[low_bound - 1 : high_bound]
    else:
        ls = []
        for i, score in enumerate(score_ls):
            now = datetime.now() - timedelta(days=day + 1)
            today_stamp = mktime(strptime(str(now), "%Y-%m-%d %H:%M:%S.%f"))
            playtime = datetime.strptime(
                score.ended_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S"
            ) + timedelta(hours=8)
            play_stamp = mktime(strptime(str(playtime), "%Y-%m-%d %H:%M:%S"))
            if play_stamp > today_stamp:
                ls.append(i)
        score_ls_filtered = [score_ls[i] for i in ls]
        if not score_ls_filtered:
            return f"近{day + 1}日内在 {GMN[mode]} 没有新增的BP成绩"
    for score_info in score_ls_filtered:
        # 判断是否开启lazer模式
        if lazer_mode:
            score_info.legacy_total_score = score_info.total_score
        if not player.lazer_mode and Mod(acronym="CL") in score_info.mods:
            score_info.mods.remove(Mod(acronym="CL"))
        if score_info.ruleset_id == 3 and not lazer_mode:
            score_info.accuracy = cal_legacy_acc(score_info.statistics)
        if not lazer_mode:
            is_hidden = any(
                i in score_info.mods
                for i in (Mod(acronym="HD"), Mod(acronym="FL"), Mod(acronym="FI"))
            )
            score_info.rank = cal_legacy_rank(score_info, is_hidden)
    msg = await draw_pfm(
        project, user, score_ls, score_ls_filtered, mode, low_bound, high_bound, day
    )
    return msg


async def draw_pfm(
    project: str,
    user: str,
    score_ls: list[NewScore],
    score_ls_filtered: list[NewScore],
    mode: str,
    low_bound: int = 0,
    high_bound: int = 0,
    day: int = 0,
) -> Union[str, BytesIO]:
    task0 = [
        get_projectimg(
            f"https://assets.ppy.sh/beatmaps/{i.beatmapset.id}/covers/list.jpg"
        )
        for i in score_ls_filtered
    ]
    task1 = [
        get_projectimg(
            f"https://assets.ppy.sh/beatmaps/{i.beatmapset.id}/covers/cover.jpg"
        )
        for i in score_ls_filtered
    ]
    bg_ls = await asyncio.gather(*task0)
    large_banner_ls = await asyncio.gather(*task1)
    bplist_len = len(score_ls_filtered)
    im = Image.new(
        "RGBA", (1420, 280 + 177 * ((bplist_len + 1) // 2 - 1)), (31, 41, 46, 255)
    )
    if project in ("prlist", "relist"):
        im.alpha_composite(BgImg1)
    else:
        im.alpha_composite(BgImg)
    draw = ImageDraw.Draw(im)
    f_div = Image.new("RGBA", (1450, 2), (255, 255, 255, 255)).convert("RGBA")
    im.alpha_composite(f_div, (0, 100))
    if project == "bp":
        uinfo = (
            f"玩家：{user} | {mode.capitalize()} 模式 | BP {low_bound} - {high_bound}"
        )
    elif project == "prlist":
        uinfo = f"玩家：{user} | {mode.capitalize()} 模式 | 近24h内上传成绩"
    elif project == "relist":
        uinfo = f"玩家：{user} | {mode.capitalize()} 模式 | 近24h内（含死亡）上传成绩"
    else:
        uinfo = f"玩家：{user} | {mode.capitalize()} 模式 | 近{day + 1}日新增 BP"
    draw.text((1388, 50), uinfo, font=Torus_SemiBold_25, anchor="rm")
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

        # mods
        if bp.mods:
            for mods_num, s_mods in enumerate(bp.mods):
                mods_bg = osufile / "mods" / f"{s_mods.acronym}.png"
                try:
                    mods_img = Image.open(mods_bg).convert("RGBA")
                    im.alpha_composite(
                        mods_img, (210 + offset + 50 * mods_num, 192 + h_num)
                    )
                except FileNotFoundError:
                    pass
            if (bp.rank == "X" or bp.rank == "S") and (
                Mod(acronym="HD") in bp.mods
                or Mod(acronym="FL") in bp.mods
                or Mod(acronym="FI") in bp.mods
            ):
                bp.rank += "H"

        # 曲名&作曲
        metadata = f"{bp.beatmapset.title} | by {bp.beatmapset.artist}"
        if len(metadata) > 30:
            metadata = metadata[:27] + "..."
        draw.text(
            (210 + offset, 135 + h_num), metadata, font=Torus_Regular_25, anchor="lm"
        )

        # 地图版本&时间
        old_time = datetime.strptime(bp.ended_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        new_time = (old_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        difficulty = bp.beatmap.version
        if len(difficulty) > 30:
            difficulty = difficulty[:27] + "..."
        difficulty = f"{bp.beatmap.difficulty_rating}★ | {difficulty}"
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
            f"{new_time}",
            font=Torus_Regular_20,
            anchor="lm",
        )

        # acc
        draw.text(
            (680 + offset, 210 + h_num),
            f"{bp.accuracy * 100:.2f}%",
            font=Torus_SemiBold_25,
            anchor="rm",
            fill=(238, 171, 0, 255),
        )

        # rank
        rank_img = osufile / "ranking" / f"ranking-{bp.rank}.png"
        rank_bg = Image.open(rank_img).convert("RGBA").resize((60, 30))
        im.alpha_composite(rank_bg, (621 + offset, 120 + h_num))

        # mapid
        draw.text(
            (680 + offset, 245 + h_num),
            f"ID: {bp.beatmap.id}",
            font=Torus_Regular_20,
            anchor="rm",
        )

        # pp
        if bp.pp:
            draw.text(
                (645 + offset, 174 + h_num),
                f"{bp.pp:.0f}",
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
    im.save(image_bytesio, "PNG")
    # 转换为 JPEG 格式
    image_bytesio.seek(0)
    image = Image.open(image_bytesio).convert("RGB")
    image_bytesio = BytesIO()
    image.save(image_bytesio, "JPEG", quality=85)
    image.close()
    return image_bytesio
