from typing import Union
from nonebot.internal.params import Depends
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot_plugin_guild_patch import GuildMessageEvent
from nonebot.params import T_State, CommandArg
from ..utils import mods2list
from ..database.models import UserData


def split_msg():
    async def dependency(event: Union[MessageEvent, GuildMessageEvent], state: T_State, msg: Message = CommandArg()):
        qq = event.user_id
        for msg_seg in event.message:
            if msg_seg.type == "at":
                qq = str(msg_seg.data.get("qq", ""))
        user_data = await UserData.get_or_none(user_id=qq)
        state['user'] = user_data.osu_id if user_data else 0
        state['mode'] = str(user_data.osu_mode) if user_data else '0'
        state['mods'] = []
        state['day'] = 0
        state['is_name'] = False
        symbol_ls = [':', '+', '：', '#', '＃']
        symbol_dic = {':': 'mode', '+': 'mods', '：': 'mode', '#': 'day', '＃': 'day'}
        dic = {}
        arg = msg.extract_plain_text().strip()
        if max([arg.find(i) for i in symbol_ls]) >= 0:
            for i in symbol_ls:
                dic[i] = arg.find(i)
            sorted_dict = sorted(dic.items(), key=lambda x: x[1])
            for i in range(len(sorted_dict) - 1):
                if sorted_dict[i][1] >= 0:
                    state[symbol_dic[sorted_dict[i][0]]] = arg[sorted_dict[i][1] + 1:sorted_dict[i + 1][1]].strip()
            if sorted_dict[-1][1] >= 0:
                state[symbol_dic[sorted_dict[-1][0]]] = arg[sorted_dict[-1][1] + 1:].strip()
            if isinstance(state['mods'], str):
                state['mods'] = mods2list(state['mods'].strip())
            index = min([arg.find(i) for i in symbol_ls if arg.find(i) >= 0])
            state['para'] = arg[:index].strip()
        else:
            state['para'] = arg.strip()
        if state['_prefix']['command'][0] in ('pr', 're', 'info', 'tbp', 'recent') and state['para']:
            state['is_name'] = True
        # 分出user和参数
        if state['para'].find(' ') > 0 and state['_prefix']['command'][0] not in ('pr', 're', 'info', 'tbp', 'recent'):
            state['user'] = state['para'][:state['para'].rfind(' ')].strip()
            state['para'] = state['para'][state['para'].rfind(' ') + 1:].strip()
            state['is_name'] = True
        elif state['para'].find(' ') > 0 and state['_prefix']['command'][0] in ('pr', 're', 'info', 'tbp', 'recent'):
            state['user'] = state['para']
        if not state['mode'].isdigit() and (int(state['mode']) < 0 or int(state['mode']) > 3):
            state['error'] = '模式应为0-3的数字！'
        if isinstance(state['day'], str) and not state['day'].isdigit() and (int(state['day']) < 0):
            state['error'] = '查询的日期应是一个正数'
        if state['user'] == 0 and not state['para']:
            state['error'] = '该账号尚未绑定，请输入 /bind 用户名 绑定账号'
        state['day'] = int(state['day'])
    return Depends(dependency)
