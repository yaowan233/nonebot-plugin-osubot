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

FILTER_PATTERN = (
    r"title\s*(!=|~=|=|~)\s*(.*?)(?=\s*(?:[:：]\s*|\+|\#|\d+\s*-\s*\d+|\w+\s*(?:!=|>=|<=|~=|=|>|<|~)|$))|"
    r"(\w+)\s*(!=|>=|<=|~=|=|>|<|~)\s*(\"[^\"]*\"|'[^']*'|[^\s,，]+)"
)
pattern = r"[:：]\s*(\w+)|[\+＋]\s*(\w+)|[#＃]\s*(\d+)|(\d+\s*-\s*\d+)|[＆&]\s*(\w+)|" + FILTER_PATTERN

BP_COMMANDS = {"bp", "pfm", "bplist", "bl", "tbp", "nb", "todaybp"}


def extract_bp_shorthands(arg: str, conditions: list[tuple[str, str, str]]) -> str:
    """Extract compact, whole-token BP filters and return the remaining arguments."""

    def add(pattern: str, callback) -> None:
        nonlocal arg

        def replace(match: re.Match) -> str:
            conditions.append(callback(match))
            return " "

        arg = re.sub(pattern, replace, arg, flags=re.IGNORECASE)

    add(
        r"(?<!\S)(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\*(?!\S)",
        lambda match: ("stars", "=", f"{match[1]}..{match[2]}"),
    )

    metric_fields = {
        "pp": "pp",
        "p": "pp",
        "acc": "accuracy",
        "a": "accuracy",
        "star": "stars",
        "sr": "stars",
        "s": "stars",
        "*": "stars",
    }

    def metric_condition(match: re.Match) -> tuple[str, str, str]:
        operator = {"+": ">=", "-": "<="}.get(match[3], "=")
        return metric_fields[match[2].lower()], operator, match[1]

    add(
        r"(?<!\S)(\d+(?:\.\d+)?)(pp|acc|star|sr|p|a|s|\*)([+-]?)(?!\S)",
        metric_condition,
    )
    add(r"(?<!\S)(\d+(?:\.\d+)?)d(?!\S)", lambda match: ("days", "<=", match[1]))
    add(r"(?<!\S)(\d+(?:\.\d+)?)h(?!\S)", lambda match: ("hours", "<=", match[1]))
    add(r"(?<!\S)fc(?!\S)", lambda _match: ("fc", "=", "true"))
    add(r"(?<!\S)nofc(?!\S)", lambda _match: ("fc", "=", "false"))
    add(r"(?<!\S)-([a-z0-9]{2,})(?!\S)", lambda match: ("mods", "!=", match[1]))
    add(r"(?<!\S)=([a-z0-9]{2,})(?!\S)", lambda match: ("mods", "=", match[1]))
    return arg


def parse_bp_filter_text(arg: str) -> tuple[list[tuple[str, str, str]], str]:
    """Parse the same filter expressions accepted by /bp and /bl."""
    conditions: list[tuple[str, str, str]] = []
    arg = extract_bp_shorthands(arg, conditions)
    for match in re.findall(FILTER_PATTERN, arg):
        if match[1]:
            conditions.append(("title", match[0], match[1].strip().strip("\"'")))
        elif match[2]:
            conditions.append((match[2], match[3], match[4].strip().strip("\"'")))
    return conditions, re.sub(FILTER_PATTERN, "", arg).strip()


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
        state["mods"] = []
        state["range"] = None
        state["day"] = 0
        state["source"] = "osu"
        state["query"] = []
        state["target"] = None
        # 官网查询统一使用当前成绩集合（lazer + stable）。
        state["is_lazer"] = True
        arg = (
            arg.extract_plain_text().strip().replace("＝", "=").replace("：", ":").replace("＆", "&").replace("＃", "#")
        )
        command = state.get("_prefix", {}).get("command", [""])[0]
        if command in BP_COMMANDS:
            arg = extract_bp_shorthands(arg, state["query"])
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
                state["query"].append(("title", match[5], match[6].strip().strip("\"'")))
            if match[7]:
                value = match[9].strip().strip("\"'")
                state["query"].append((match[7], match[8], value))
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
