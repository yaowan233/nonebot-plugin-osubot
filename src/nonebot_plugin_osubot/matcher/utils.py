import re

from nonebot.internal.params import Depends
from nonebot_plugin_alconna import At, UniMsg
from nonebot.params import T_State, CommandArg
from nonebot.internal.adapter import Event, Message
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..utils import extract_beatmap_id, extract_beatmapset_id, mods2list, parse_mode
from ..api import get_uid_by_name, osu_api
from ..exceptions import NetworkError
from ..database import UserData, SbUserData

pattern = (
    r"[:：]\s*(\w+)|[\+＋]\s*([\w,，]+)|[#＃]\s*(\d+)|(\d+\s*-\s*\d+)|[＆&]\s*(\w+)|"
    r"title\s*([=~]+)\s*(.*?)(?=\s*(?:[:：]\s*|\+|\#|\d+\s*-\s*\d+|\w+\s*([><=~]+)\s*[\w\.]+|$))|"
    r"(\w+)\s*([><=~]+)\s*([\w\.]+)"
)


def split_msg():
    async def dependency(event: Event, state: T_State, msg: UniMsg, arg: Message = CommandArg()):
        qq = event.get_user_id()
        if msg.has(At):
            qq = msg.get(At)[0].target
        async with get_session() as session:
            user_data = await session.scalar(select(UserData).where(UserData.user_id == qq))
        state["user"] = user_data.osu_id if user_data else 0
        state["mode"] = str(user_data.osu_mode) if user_data else "0"
        state["username"] = user_data.osu_name if user_data else ""
        state["bound_user"] = state["user"]
        state["bound_mode"] = state["mode"]
        state["bound_username"] = state["username"]
        state["mods"] = []
        state["range"] = None
        state["day"] = 0
        state["source"] = "osu"
        state["query"] = []
        state["target"] = None
        state["is_lazer"] = True if not user_data else user_data.lazer_mode
        arg = (
            arg.extract_plain_text().strip().replace("＝", "=").replace("：", ":").replace("＆", "&").replace("＃", "#")
        )
        command = state.get("_prefix", {}).get("command", [""])[0]
        set_commands = {"bmap", "bm", "osudl", "dl", "反键"}
        if command in set_commands:
            url_target = extract_beatmapset_id(arg)
            if not url_target and (linked_map_id := extract_beatmap_id(arg)):
                map_data = await osu_api("map", map_id=int(linked_map_id))
                url_target = str(map_data["beatmapset_id"])
        else:
            url_target = extract_beatmap_id(arg)
        if url_target:
            state["target"] = url_target
            arg = re.sub(r"(?:https?://)?osu\.ppy\.sh/\S+", "", arg)
        matches = re.findall(pattern, arg)
        for match in matches:
            if match[0]:
                state["mode"] = match[0]
            if match[1]:
                state["mods"] = mods2list(match[1])
            if match[2]:
                state["day"] = int(match[2])
            if match[3]:
                low, high = (int(value.strip()) for value in match[3].split("-"))
                state["range"] = f"{min(low, high)}-{max(low, high)}"
            if match[4]:
                source = {"sb": "ppysb", "ppysb": "ppysb"}
                state["source"] = source.get(match[4], "osu")
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
            state["username"] = arg.strip()
            try:
                user = await get_uid_by_name(arg.strip(), state["source"])
                state["user"] = user
            except NetworkError:
                state["error"] = f"在 {state['source']} 服务器没有找到用户: {arg.strip()}"
        if state["source"] == "ppysb":
            normalized_mode = parse_mode(state["mode"], allow_special=True)
            if normalized_mode is None:
                state["error"] = (
                    "模式应为0-8(没有7)！\n0: std\n1: taiko\n2: ctb\n3: mania\n4-6: SB服 RX 模式\n8: SB服 AP 模式"
                )
            else:
                state["mode"] = normalized_mode
        else:
            normalized_mode = parse_mode(state["mode"])
            if normalized_mode is None:
                state["error"] = "模式应为 std、taiko、catch、mania，或数字 0-3"
            else:
                state["mode"] = normalized_mode
        if isinstance(state["day"], str) and (not state["day"].isdigit() or int(state["day"]) < 0):
            state["error"] = "查询的日期应是一个正数"
        if state["user"] == 0:
            state["error"] = "该账号尚未绑定，请输入 /bind 用户名 绑定账号"
        if state["source"] == "ppysb" and not arg.strip():
            async with get_session() as session:
                sb_user_data = await session.scalar(select(SbUserData).where(SbUserData.user_id == qq))
            if sb_user_data:
                state["user"] = sb_user_data.osu_id
                state["username"] = sb_user_data.osu_name
            else:
                state["error"] = "该账号尚未绑定 sb 服务器，请输入 /sbbind 用户名 绑定账号"

    return Depends(dependency)
