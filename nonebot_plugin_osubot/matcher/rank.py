import datetime

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, Bot
from nonebot.params import T_State
from .utils import split_msg
from ..database.models import UserData, InfoData


group_pp_rank = on_command('群内排名', priority=11, block=True)


@group_pp_rank.handle(parameterless=[split_msg()])
async def _(event: GroupMessageEvent, state: T_State, bot: Bot):
    if 'error' in state:
        await group_pp_rank.finish(MessageSegment.reply(event.message_id) + state['error'])
    mode = state['mode']
    group_id = event.group_id
    group_member = await bot.get_group_member_list(group_id=group_id)
    user_id_ls = [i['user_id'] for i in group_member]
    binded_id = await UserData.filter(user_id__in=user_id_ls).values_list('osu_id', flat=True)
    info_ls = await InfoData.filter(osu_id__in=binded_id).filter(osu_mode=mode).filter(date=datetime.date.today()).order_by('-pp').all()
    s = ''
    for info in info_ls[:20]:
        if info.pp < 100:
            continue
        user_data = await UserData.filter(osu_id=info.osu_id).first()
        for user in group_member:
            if int(user['user_id']) == user_data.user_id:
                name = user['card'] or user.get('nickname', '')
                break
        else:
            raise Exception('这不可能发生的')
        s += f'{name} {int(info.pp)}pp 全球：{info.g_rank} 国内：{info.c_rank}\n'
    await group_pp_rank.finish(s[:-1])

