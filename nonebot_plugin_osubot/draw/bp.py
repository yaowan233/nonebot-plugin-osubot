import asyncio
from datetime import datetime, timedelta
from time import strptime, mktime
from typing import List, Union, Optional
from nonebot.adapters.onebot.v11 import MessageSegment

from ..schema import Score
from ..api import osu_api
from ..utils import GMN
from ..mods import get_mods_list

from .utils import DataText, draw_text, image2bytesio
from .static import *


async def draw_bp(project: str, uid: int, mode: str, mods: Optional[List],
                  low_bound: int = 0, high_bound: int = 0) -> Union[str, MessageSegment]:
    bp_info = await osu_api('bp', uid, mode)
    if isinstance(bp_info, str):
        return bp_info
    score_ls = [Score(**i) for i in bp_info]
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
            score_ls = [score_ls[i] for i in mods_ls]
        else:
            score_ls = score_ls[low_bound - 1: high_bound]
    elif project == 'tbp':
        ls = []
        for i, score in enumerate(score_ls):
            today = datetime.now().date()
            today_stamp = mktime(strptime(str(today), '%Y-%m-%d'))
            playtime = datetime.strptime(score.created_at.replace('Z', ''), '%Y-%m-%dT%H:%M:%S') + timedelta(
                hours=8)
            play_stamp = mktime(strptime(str(playtime), '%Y-%m-%d %H:%M:%S'))

            if play_stamp > today_stamp:
                ls.append(i)
        score_ls = [score_ls[i] for i in ls]
        if not score_ls:
            return f'今天在 {GMN[mode]} 没有新增的BP成绩'
    msg = await draw_pfm(project, user, score_ls, mode, low_bound, high_bound)
    return msg


async def draw_pfm(project: str, user: str, score_ls: List[Score], mode: str, low_bound: int = 0, high_bound: int = 0) -> \
        Union[str, MessageSegment]:
    bplist_len = len(score_ls)
    im = Image.new('RGBA', (1500, 180 + 82 * (bplist_len - 1)), (31, 41, 46, 255))
    im.alpha_composite(BgImg)
    f_div = Image.new('RGBA', (1500, 2), (255, 255, 255, 255)).convert('RGBA')
    im.alpha_composite(f_div, (0, 100))
    if project == 'bp':
        uinfo = f"{user} | {mode.capitalize()} 模式 | BP {low_bound} - {high_bound}"
    else:
        uinfo = f"{user} | {mode.capitalize()} 模式 | 今日新增 BP"
    w_user = DataText(1450, 50, 25, uinfo, Torus_SemiBold, anchor='rm')
    im = draw_text(im, w_user)
    for num, bp in enumerate(score_ls):
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
        rank_bp = DataText(15, 144 + h_num, 20, num + 1, Torus_Regular, anchor='lm')
        im = draw_text(im, rank_bp)
        # rank
        rank_img = osufile / 'ranking' / f'ranking-{bp.rank}.png'
        rank_bg = Image.open(rank_img).convert('RGBA').resize((64, 32))
        im.alpha_composite(rank_bg, (45, 128 + h_num))
        # 曲名&作曲
        w_title_artist = DataText(125, 130 + h_num, 20, f'{bp.beatmapset.title}'
                                                        f' | by {bp.beatmapset.artist}', Torus_Regular,
                                  anchor='lm')
        im = draw_text(im, w_title_artist)
        # 地图版本&时间
        old_time = datetime.strptime(bp.created_at.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
        new_time = (old_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        w_version_time = DataText(125, 158 + h_num, 18, f'{bp.beatmap.version} | {new_time}', Torus_Regular,
                                  anchor='lm')
        im = draw_text(im, w_version_time, color=(238, 171, 0, 255))
        # acc
        w_acc = DataText(1250, 130 + h_num, 22, f'{bp.accuracy * 100:.2f}%', Torus_SemiBold, anchor='lm')
        im = draw_text(im, w_acc, color=(238, 171, 0, 255))
        # mapid
        w_mapid = DataText(1250, 158 + h_num, 18, f'ID: {bp.beatmap.id}', Torus_Regular, anchor='lm')
        im = draw_text(im, w_mapid)
        # pp
        w_pp = DataText(1420, 140 + h_num, 25, int(bp.pp), Torus_SemiBold, anchor='rm')
        im = draw_text(im, w_pp, (255, 102, 171, 255))
        w_n_pp = DataText(1450, 140 + h_num, 25, 'pp', Torus_SemiBold, anchor='rm')
        im = draw_text(im, w_n_pp, (209, 148, 176, 255))
        # 分割线
        div = Image.new('RGBA', (1450, 2), (46, 53, 56, 255)).convert('RGBA')
        im.alpha_composite(div, (25, 180 + h_num))
        await asyncio.sleep(0)

    base = image2bytesio(im)
    msg = MessageSegment.image(base)
    return msg
