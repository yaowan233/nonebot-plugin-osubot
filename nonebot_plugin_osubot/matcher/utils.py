from nonebot.internal.adapter import Event, Message
from nonebot.internal.params import Depends
from nonebot.params import T_State, CommandArg
from nonebot_plugin_alconna import UniMsg, At

from ..utils import mods2list
from ..database.models import UserData


def split_msg():
    async def dependency(
        event: Event, state: T_State, msg: UniMsg, arg: Message = CommandArg()
    ):
        qq = event.get_user_id()
        if msg.has(At):
            qq = msg.get(At)[0].target
        user_data = await UserData.get_or_none(user_id=int(qq))
        state["user"] = user_data.osu_id if user_data else 0
        state["mode"] = str(user_data.osu_mode) if user_data else "0"
        state["mods"] = []
        state["day"] = 0
        state["is_name"] = False
        symbol_ls = [":", "+", "：", "#", "＃"]
        symbol_dic = {":": "mode", "+": "mods", "：": "mode", "#": "day", "＃": "day"}
        double_command = ("bp", "score")
        dic = {}
        arg = arg.extract_plain_text().strip()
        if max([arg.find(i) for i in symbol_ls]) >= 0:
            for i in symbol_ls:
                dic[i] = arg.find(i)
            sorted_dict = sorted(dic.items(), key=lambda x: x[1])
            for i in range(len(sorted_dict) - 1):
                if sorted_dict[i][1] >= 0:
                    state[symbol_dic[sorted_dict[i][0]]] = arg[
                        sorted_dict[i][1] + 1 : sorted_dict[i + 1][1]
                    ].strip()
            if sorted_dict[-1][1] >= 0:
                state[symbol_dic[sorted_dict[-1][0]]] = arg[
                    sorted_dict[-1][1] + 1 :
                ].strip()
            if isinstance(state["mods"], str):
                state["mods"] = mods2list(state["mods"].strip())
            index = min([arg.find(i) for i in symbol_ls if arg.find(i) >= 0])
            state["para"] = arg[:index].strip()
        else:
            state["para"] = arg.strip()
        if " " in state["para"]:
            ls = state["para"].split(" ")
            if state["_prefix"]["command"][0] in double_command:
                state["para"] = ls[-1]
                state["user"] = " ".join(ls[:-1])
            elif is_num_hyphen_num(ls[-1]):
                state["para"] = ls[-1]
                state["user"] = " ".join(ls[:-1])
            elif is_num_hyphen_num(ls[0]):
                state["para"] = ls[0]
                state["user"] = " ".join(ls[1:])
            else:
                state["user"] = state["para"]
            state["is_name"] = True
        elif state["para"]:
            if (
                not is_num_hyphen_num(state["para"])
                and state["_prefix"]["command"][0] not in double_command
            ):
                state["user"] = state["para"]
                state["is_name"] = True
        # 判断参数是否合法
        if not state["mode"].isdigit() or (
            int(state["mode"]) < 0 or int(state["mode"]) > 3
        ):
            state["error"] = "模式应为0-3的数字！"
        if (
            isinstance(state["day"], str)
            and not state["day"].isdigit()
            and (int(state["day"]) < 0)
        ):
            state["error"] = "查询的日期应是一个正数"
        if state["user"] == 0 and not state["user"]:
            state["error"] = "该账号尚未绑定，请输入 /bind 用户名 绑定账号"
        state["day"] = int(state["day"])

    return Depends(dependency)


def is_num_hyphen_num(s: str):
    if s.count("-") != 1:
        return False
    s = s.split("-")
    return s[0].isdigit() and s[1].isdigit()
