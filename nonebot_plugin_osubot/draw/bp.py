import asyncio
from datetime import datetime, timedelta, date
from time import strptime, mktime
from typing import List, Union, Optional

from PIL import ImageDraw, UnidentifiedImageError
from nonebot.adapters.onebot.v11 import MessageSegment

from ..schema import Score
from ..api import osu_api
from ..utils import GMN
from ..mods import get_mods_list
from ..file import get_projectimg

from .utils import image2bytesio, draw_fillet
from .static import *


async def draw_bp(project: str, uid: int, mode: str, mods: Optional[List], low_bound: int = 0, high_bound: int = 0,
                  day: int = 0, is_name: bool = False) -> Union[str, MessageSegment]:
    bp_info = await osu_api('bp', uid, mode, is_name=is_name)
    if isinstance(bp_info, str):
        return bp_info
    score_ls = [Score(**i) for i in bp_info]
    if not bp_info:
        return f'未查询到在 {GMN[mode]} 的游玩记录'
    user = bp_info[0]['user']['username']
    if project == 'bp':
        if mods:
            mods_ls = get_mods_list(score_ls, mods)
            if low_bound > len(mods_ls):
                return f'未找到开启 {"|".join(mods)} Mods的成绩'
            if high_bound > len(mods_ls):
                mods_ls = mods_ls[low_bound - 1:]
            else:
                mods_ls = mods_ls[low_bound - 1: high_bound]
            score_ls_filtered = [score_ls[i] for i in mods_ls]
        else:
            score_ls_filtered = score_ls[low_bound - 1: high_bound]
    else:
        ls = []
        for i, score in enumerate(score_ls):
            today = date.today() - timedelta(days=day)
            today_stamp = mktime(strptime(str(today), '%Y-%m-%d'))
            playtime = datetime.strptime(score.created_at.replace('Z', ''), '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8)
            play_stamp = mktime(strptime(str(playtime), '%Y-%m-%d %H:%M:%S'))
            if play_stamp > today_stamp:
                ls.append(i)
        score_ls_filtered = [score_ls[i] for i in ls]
        if not score_ls_filtered:
            return f'近{day + 1}日内在 {GMN[mode]} 没有新增的BP成绩'
    msg = await draw_pfm(project, user, score_ls, score_ls_filtered, mode, low_bound, high_bound, day)
    return msg


async def draw_pfm(project: str, user: str, score_ls: List[Score], score_ls_filtered: List[Score],
                   mode: str, low_bound: int = 0, high_bound: int = 0,
                   day: int = 0) -> Union[str, MessageSegment]:
    tasks = [get_projectimg(f'https://assets.ppy.sh/beatmaps/{i.beatmapset.id}/covers/card.jpg')
             for i in score_ls_filtered]
    bg_ls = await asyncio.gather(*tasks)
    bplist_len = len(score_ls_filtered)
    im = Image.new('RGBA', (1500, 180 + 82 * (bplist_len - 1)), (31, 41, 46, 255))
    im.alpha_composite(BgImg)
    draw = ImageDraw.Draw(im)
    f_div = Image.new('RGBA', (1500, 2), (255, 255, 255, 255)).convert('RGBA')
    im.alpha_composite(f_div, (0, 100))
    if project == 'bp':
        uinfo = f"{user} | {mode.capitalize()} 模式 | BP {low_bound} - {high_bound}"
    else:
        uinfo = f"{user} | {mode.capitalize()} 模式 | 近{day + 1}日新增 BP"
    draw.text((1480, 50), uinfo, font=Torus_SemiBold_25, anchor='rm')
    for num, bp in enumerate(score_ls_filtered):
        h_num = 82 * num
        # mods
        if bp.mods:
            for mods_num, s_mods in enumerate(bp.mods):
                mods_bg = osufile / 'mods' / f'{s_mods}.png'
                mods_img = Image.open(mods_bg).convert('RGBA')
                im.alpha_composite(mods_img, (1000 + 50 * mods_num, 126 + h_num))
            if (bp.rank == 'X' or bp.rank == 'S') and ('HD' in bp.mods or 'FL' in bp.mods):
                bp.rank += 'H'
        # BP排名
        index = score_ls.index(bp)
        draw.text((15, 144 + h_num), str(index + 1), font=Torus_Regular_20, anchor='lm')
        # 获取谱面banner
        try:
            bg = Image.open(bg_ls[num]).convert('RGBA').resize((157, 55))
            bg_imag = draw_fillet(bg, 10)
            im.alpha_composite(bg_imag, (45, 114 + h_num))
        except UnidentifiedImageError:
            ...
        # rank
        rank_img = osufile / 'ranking' / f'ranking-{bp.rank}.png'
        rank_bg = Image.open(rank_img).convert('RGBA').resize((32, 16))
        im.alpha_composite(rank_bg, (1345, 124 + h_num))
        # 曲名&作曲
        metadata = f'{bp.beatmapset.title} | by {bp.beatmapset.artist}'
        # 如果曲名&作曲的长度超过75，就截断它
        if len(metadata) > 75:
            metadata = metadata[:72] + '...'
        # 写入曲名&作曲
        draw.text((215, 125 + h_num), metadata, font=Torus_Regular_20, anchor='lm')
        # 地图版本&时间
        old_time = datetime.strptime(bp.created_at.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
        new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        # 如果难度名的长度超过50，就截断它
        difficulty = bp.beatmap.version
        if len(difficulty) > 50:
            difficulty = difficulty[:47] + '...'
        # 写入难度名
        difficulty = f'{bp.beatmap.difficulty_rating}★ | {difficulty} | {new_time}'
        draw.text((215, 158 + h_num), difficulty, font=Torus_Regular_20, anchor='lm', fill=(238, 171, 0, 255))
        # acc
        draw.text((1265, 130 + h_num), f'{bp.accuracy * 100:.2f}%', font=Torus_SemiBold_20,
                  anchor='lm', fill=(238, 171, 0, 255))
        # mapid
        draw.text((1265, 158 + h_num), f'ID: {bp.beatmap.id}', font=Torus_Regular_20, anchor='lm')
        # pp
        draw.text((1450, 140 + h_num), f'{bp.pp:.0f}', font=Torus_SemiBold_25, anchor='rm', fill=(255, 102, 171, 255))
        draw.text((1480, 140 + h_num), 'pp', font=Torus_SemiBold_25, anchor='rm', fill=(209, 148, 176, 255))
        # 分割线
        div = Image.new('RGBA', (1450, 2), (46, 53, 56, 255)).convert('RGBA')
        im.alpha_composite(div, (25, 180 + h_num))
        await asyncio.sleep(0)
    base = image2bytesio(im)
    im.close()
    msg = MessageSegment.image(base)
    return msg
