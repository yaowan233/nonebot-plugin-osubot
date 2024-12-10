import re

from nonebot.internal.params import Depends
from nonebot_plugin_alconna import At, UniMsg
from nonebot.params import T_State, CommandArg
from nonebot.internal.adapter import Event, Message

from ..utils import mods2list
from ..database.models import UserData

pattern = (
    r"[:：]\s*(\w+)|[\+＋]\s*(\w+)|[#＃]\s*(\d+)|(\d+\s*-\s*\d+)|[＆&]\s*(\w+)|"
    r"title\s*([=~]+)\s*(.*?)(?=\s*(?:[:：]\s*|\+|\#|\d+\s*-\s*\d+|\w+\s*([><=~]+)\s*[\w\.]+|$))|"
    r"(\w+)\s*([><=~]+)\s*([\w\.]+)"
)


def split_msg():
    async def dependency(event: Event, state: T_State, msg: UniMsg, arg: Message = CommandArg()):
        qq = event.get_user_id()
        if msg.has(At):
            qq = msg.get(At)[0].target
        user_data = await UserData.get_or_none(user_id=qq)
        state["user"] = user_data.osu_id if user_data else 0
        state["mode"] = str(user_data.osu_mode) if user_data else "0"
        state["username"] = user_data.osu_name if user_data else ""
        state["mods"] = []
        state["range"] = None
        state["day"] = 0
        state["is_name"] = False
        state["query"] = []
        state["target"] = None
        state["is_lazer"] = True if not user_data else user_data.lazer_mode
        arg = arg.extract_plain_text().strip()
        matches = re.findall(pattern, arg)
        for match in matches:
            if match[0]:
                state["mode"] = match[0]
            if match[1]:
                state["mods"] = mods2list(match[1])
            if match[2]:
                state["day"] = int(match[2])
            if match[3]:
                state["range"] = match[3]
            if match[6]:
                state["query"].append(("title", match[5], match[6]))
            if match[8]:
                state["query"].append((match[8], match[9], match[10]))
                if match[9] in [">", "<", ">=", "<="]:
                    try:
                        float(match[10]) if "." in match[10] else int(match[10])
                    except ValueError:
                        state["error"] = f"'{match[10]}' 不能进行数值比较"
        arg = re.sub(pattern, "", arg)
        arg = " " + arg
        matches = re.findall(r"(?<=\s)\d+(?=\s|$)", arg)
        if matches:
            last_match = matches[-1]  # 获取最后一个匹配的数字
            state["target"] = last_match
            arg = re.sub(r"(?<=\s)\d+(?=\s|$)", "", arg)
        if arg.strip():
            state["user"] = arg.strip()
            state["username"] = arg.strip()
            state["is_name"] = True
        if not state["mode"].isdigit() or not (0 <= int(state["mode"]) <= 3):
            state["error"] = "模式应为0-3！\n0: std\n1:taiko\n2:ctb\n3: mania"
        if isinstance(state["day"], str) and (not state["day"].isdigit() or int(state["day"]) < 0):
            state["error"] = "查询的日期应是一个正数"
        if state["user"] == 0:
            state["error"] = "该账号尚未绑定，请输入 /bind 用户名 绑定账号"

    return Depends(dependency)
