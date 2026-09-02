"""好友功能：查询好友列表与互关状态（移植自 yumu-bot 的 !friend / !f）。

用法（触发前缀已改为 /）：
  /friend            查看自己的好友列表（单张图片最多 50 位）
  /friend :pp        按 PP 排序（:acc/:pc/:pt/:th/:t/:u/:c/:n/:o/:m，
                     后缀 + 或 2 表示升序，- 表示降序）
  /friend 1-30       查看第 1-30 位好友
  /friend pp>=300 mutual=true country=JP   组合筛选
  /friend <玩家名>   查询与对方是否互关（mutual）

数据来源：osu! API v2 GET /friends，需要用户级 OAuth 令牌（friends.read）。
首次使用 /friend 时会自动发送授权链接，各绑定用户持有自己的令牌。
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from nonebot import on_command
from nonebot.internal.adapter import Event, Message
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_alconna.uniseg import Receipt
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..api import (
    get_osu_user,
    get_user_friends,
)
from ..database import UserData, UserOAuthData
from ..draw.friend import draw_friend_list
from ..exceptions import NetworkError
from ..friend_oauth import (
    OAuthAuthorizationError,
    OAuthAuthorizationTimeout,
    begin_authorization,
    complete_authorization,
    delete_oauth,
    discard_authorization,
    get_valid_oauth,
    wait_for_authorization,
)

friend = on_command("friend", aliases={"f"}, priority=11, block=True)
FRIEND_LIST_RENDER_LIMIT = 50


async def _recall_oauth_message(receipt: Receipt | None) -> None:
    """尽力撤回包含一次性 OAuth URL 的消息。"""
    if receipt is None:
        return
    try:
        await receipt.recall()
    except Exception as error:
        # 部分适配器虽然暴露撤回接口，仍可能因权限或消息时限拒绝操作；
        # 撤回失败不应破坏已经完成的授权。
        logger.debug(f"撤回 OAuth 授权链接失败: {error}")


# ===========================================================================
# /friend：好友列表 / 互关查询
# ===========================================================================
@friend.handle()
async def _friend(event: Event, arg: Message = CommandArg()):
    platform_user_id = event.get_user_id()

    async with get_session() as session:
        user_data = await session.scalar(select(UserData).where(UserData.user_id == platform_user_id))
    if not user_data:
        await friend.finish("该账号尚未绑定，请输入 /bind 用户名 绑定账号")
    oauth = await get_valid_oauth(platform_user_id)
    if oauth is None:
        authorization = None
        authorization_message = None
        try:
            authorization = await begin_authorization()
            expires_minutes = max(1, (authorization.expires_in + 59) // 60)
            authorization_message = await UniMessage.text(
                f"首次查询需要授权读取 osu! 好友列表。请在 {expires_minutes} 分钟内点击链接完成授权，"
                f"完成后本次查询会自动继续：\n{authorization.authorize_url}"
            ).send(reply_to=True)
            code = await wait_for_authorization(authorization)
            oauth = await complete_authorization(
                platform_user_id,
                code,
                authorization.redirect_uri,
            )
        except OAuthAuthorizationTimeout:
            return
        except NetworkError as error:
            await friend.finish(f"OAuth 授权失败：{error}")
        finally:
            await _recall_oauth_message(authorization_message)
            if authorization is not None:
                await discard_authorization(authorization)
        await friend.send(f"OAuth 授权成功，已关联 osu! 账号 {oauth.osu_name}。正在继续查询好友……")

    text = arg.extract_plain_text().strip()
    sort, text = _parse_sort(text)
    range_match = re.match(r"#?\s*(\d+)(?:\s*-\s*(\d+))?", text)
    start = end = None
    if range_match and range_match.start() == 0:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else start
        text = text[range_match.end() :].strip()

    conditions, rest = _parse_conditions(text)

    try:
        friends = await get_user_friends(oauth.access_token)
    except NetworkError as e:
        if "HTTP 401" in str(e):
            await delete_oauth(platform_user_id)
            await friend.finish(f"无法获取好友列表：{e}\n授权已失效，请重新发送 /friend 完成授权。")
        await friend.finish(f"无法获取好友列表：{e}\n请稍后重试。")

    # 玩家名模式：查询互关
    if rest:
        await _handle_pair(oauth, friends, rest)
        return

    # 列表模式
    if not friends:
        await friend.finish("你的好友列表还是空的哦～")

    sorted_friends = _sort_friends(friends, sort)
    filtered = _filter_friends(sorted_friends, conditions)
    if not filtered:
        await friend.finish("没有找到符合条件的好友，试试调整筛选条件吧")
    total = len(filtered)

    start = start or 1
    end = end or total
    if end < start:
        start, end = end, start  # 反向范围自动纠正
    end = min(end, total, start + FRIEND_LIST_RENDER_LIMIT - 1)

    selected = filtered[start - 1 : end]
    if not selected:
        await friend.finish(f"好友数量不足，当前符合条件的好友共 {total} 位。")

    try:
        img = await draw_friend_list(
            {
                "me_name": oauth.osu_name,
                "me_uid": oauth.osu_id,
                "me_avatar": f"https://a.ppy.sh/{oauth.osu_id}",
                "sort_label": _sort_label(sort),
                "total": total,
                "mutual_count": sum(1 for f in filtered if f.mutual),
                "online_count": sum(1 for f in filtered if f.target and f.target.is_online),
                "start": start,
                "end": start + len(selected) - 1,
                "friends": [
                    {
                        "avatar": f.target.avatar_url,
                        "name": f.target.username,
                        "uid": f.target_id,
                        "country": (f.target.country_code or "")[:2],
                        "online": f.target.is_online,
                        "mutual": f.mutual,
                        "supporter": f.target.is_supporter,
                    }
                    for f in selected
                ],
            }
        )
    except Exception as e:
        logger.opt(exception=e).error("渲染好友列表失败")
        await friend.finish(f"渲染好友列表失败：{e}")
    await UniMessage.image(raw=img).finish(reply_to=True)


async def _handle_pair(oauth: UserOAuthData, friends: list, name_text: str) -> None:
    """互关查询：/friend <玩家名>"""
    try:
        partner = await get_osu_user(name_text)
    except NetworkError as e:
        await friend.finish(f"在 osu! 服务器没有找到玩家: {name_text}（{e}）")
    partner_id = int(partner["id"])
    partner_name = partner["username"]

    if partner_id == oauth.osu_id:
        await friend.finish("你自己与你自己就是最好的朋友。")

    my_following = next((f for f in friends if f.target_id == partner_id), None)

    # 若对方也完成了 OAuth 授权，可精确判断对方是否关注我
    partner_followed_me: bool | None = None
    partner_friend_count: int | None = None
    async with get_session() as session:
        partner_oauth = await session.scalar(select(UserOAuthData).where(UserOAuthData.osu_id == partner_id))
    if partner_oauth is not None:
        try:
            partner_oauth = await get_valid_oauth(partner_oauth.user_id)
            if partner_oauth is None:
                raise OAuthAuthorizationError("对方当前绑定账号与 OAuth 授权不一致")
            partner_friends = await get_user_friends(partner_oauth.access_token)
            partner_friend_count = len(partner_friends)
            partner_followed_me = any(f.target_id == oauth.osu_id for f in partner_friends)
        except Exception:
            partner_followed_me = None
    elif my_following is not None:
        # 对方未授权时，用我这边好友条目的 mutual 标记推断
        partner_followed_me = my_following.mutual

    if my_following is not None:
        if partner_followed_me:
            text_msg = f"恭喜！你已经与 {partner_name} 互相成为好友了（mutual）。"
        else:
            text_msg = f"你已经添加了 {partner_name} 作为你的好友，但对方似乎还没有添加你。"
    elif partner_followed_me is None:
        text_msg = f"你还没有将 {partner_name} 添加为你的好友，并且对方没有完成 OAuth 授权，还不知道有没有添加你。"
    elif partner_followed_me:
        text_msg = f"你还没有将 {partner_name} 添加为你的好友，但对方似乎已经悄悄添加了你。"
    else:
        text_msg = "你们暂未互相成为好友。或许可以考虑一下？"

    extra = f"\n你的好友数：{len(friends)}"
    if partner_friend_count is not None:
        extra += f" ｜ {partner_name} 的好友数：{partner_friend_count}"
    await friend.finish(text_msg + extra)


# ===========================================================================
# 排序 / 筛选
# ===========================================================================
_SORT_FIELDS = {
    "p": "pp",
    "pp": "pp",
    "performance": "pp",
    "a": "acc",
    "acc": "acc",
    "accuracy": "acc",
    "pc": "pc",
    "playcount": "pc",
    "pt": "pt",
    "playtime": "pt",
    "th": "th",
    "h": "th",
    "tth": "th",
    "totalhits": "th",
    "t": "time",
    "time": "time",
    "seen": "time",
    "u": "uid",
    "uid": "uid",
    "c": "country",
    "country": "country",
    "n": "name",
    "name": "name",
    "o": "online",
    "on": "online",
    "online": "online",
    "m": "mutual",
    "mu": "mutual",
    "mutual": "mutual",
}

_SORT_DEFAULT_DIRECTIONS = {
    "pp": "desc",
    "acc": "desc",
    "pc": "desc",
    "pt": "desc",
    "th": "desc",
    "time": "asc",
    "uid": "asc",
    "country": "asc",
    "name": "asc",
    "online": "desc",
    "mutual": "desc",
}

SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True)
class FriendSort:
    field: str
    direction: SortDirection


_SORT_LABELS = {
    "pp": "PP",
    "acc": "ACC",
    "pc": "游玩次数",
    "pt": "游玩时长",
    "th": "总击打",
    "time": "最后上线",
    "uid": "UID",
    "country": "国家/地区",
    "name": "名字",
    "online": "在线",
    "mutual": "互关",
}


def _parse_sort(text: str) -> tuple[FriendSort | None, str]:
    """解析开头的 :xxx 排序标记。"""
    m = re.match(r":\s*([a-z]+)([+\-]|2)?", text, re.IGNORECASE)
    if not m:
        return None, text
    sort_type = _SORT_FIELDS.get(m.group(1).lower())
    if sort_type is None:
        # 未识别的排序标记视为玩家名的一部分（如 :mode），直接透传
        return None, text
    suffix = m.group(2)
    direction: SortDirection = (
        "asc" if suffix in ("+", "2") else "desc" if suffix == "-" else _SORT_DEFAULT_DIRECTIONS[sort_type]
    )
    return FriendSort(sort_type, direction), text[m.end() :].strip()


def _sort_friends(friends: list, sort: FriendSort | None) -> list:
    """按 yumu-bot 语义排序；无排序时按名字升序（确定性输出）。"""
    if sort is None:
        return sorted(friends, key=lambda f: (f.target.username or "").lower())

    def pp(f):
        return (
            f.target.statistics.pp if f.target and f.target.statistics and f.target.statistics.pp is not None else 0.0
        )

    def acc(f):
        return (
            f.target.statistics.hit_accuracy
            if f.target and f.target.statistics and f.target.statistics.hit_accuracy is not None
            else 0.0
        )

    def num(key):
        def getter(f):
            stats = f.target.statistics if f.target else None
            if stats is None:
                return 0
            return {
                "pc": stats.play_count,
                "pt": stats.play_time,
                "th": stats.total_hits,
            }.get(key, 0) or 0

        return getter

    def last_visit(f):
        if f.target and f.target.last_visit:
            try:
                value = datetime.fromisoformat(f.target.last_visit.replace("Z", "+00:00"))
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.timestamp()
            except ValueError:
                return float("-inf")
        return float("-inf")

    reverse = sort.direction == "desc"

    if sort.field == "pp":
        return sorted(friends, key=pp, reverse=reverse)
    if sort.field == "acc":
        return sorted(friends, key=acc, reverse=reverse)
    if sort.field in ("pc", "pt", "th"):
        return sorted(friends, key=num(sort.field), reverse=reverse)
    if sort.field == "time":
        return sorted(friends, key=last_visit, reverse=reverse)
    if sort.field == "uid":
        return sorted(friends, key=lambda f: f.target_id, reverse=reverse)
    if sort.field == "country":
        return sorted(
            friends,
            key=lambda f: (f.target.country_code or "") if f.target else "",
            reverse=reverse,
        )
    if sort.field == "name":
        return sorted(friends, key=lambda f: (f.target.username or "").lower(), reverse=reverse)
    if sort.field == "online":
        return sorted(friends, key=lambda f: bool(f.target and f.target.is_online), reverse=reverse)
    if sort.field == "mutual":
        return sorted(friends, key=lambda f: bool(f.mutual), reverse=reverse)
    return sorted(friends, key=lambda f: (f.target.username or "").lower())


def _sort_label(sort: FriendSort | None) -> str:
    if sort is None:
        return "默认"
    label = _SORT_LABELS.get(sort.field, sort.field)
    return f"{label}{' ↑' if sort.direction == 'asc' else ' ↓'}"


_CONDITION_PATTERN = re.compile(r'(\w+)\s*(!=|>=|<=|~=|~|=|>|<)\s*("[^"]*"|\'[^\']*\'|\S+)')

_FIELD_MAP = {
    "name": "username",
    "username": "username",
    "user": "username",
    "n": "username",
    "id": "id",
    "uid": "id",
    "i": "id",
    "country": "country",
    "code": "country",
    "c": "country",
    "mutual": "mutual",
    "mu": "mutual",
    "m": "mutual",
    "online": "online",
    "on": "online",
    "o": "online",
    "active": "active",
    "e": "active",
    "bot": "bot",
    "b": "bot",
    "deleted": "deleted",
    "del": "deleted",
    "d": "deleted",
    "supporter": "supporter",
    "vip": "supporter",
    "v": "supporter",
    "pp": "pp",
    "p": "pp",
    "performance": "pp",
    "acc": "acc",
    "accuracy": "acc",
    "a": "acc",
    "pc": "pc",
    "playcount": "pc",
    "pt": "pt",
    "playtime": "pt",
    "th": "th",
    "h": "th",
    "tth": "th",
    "totalhits": "th",
    "level": "level",
    "lv": "level",
    "l": "level",
    "combo": "max_combo",
    "cb": "max_combo",
    "rank": "global_rank",
    "ranking": "global_rank",
    "k": "global_rank",
    "ssh": "ssh",
    "ss": "ss",
    "sh": "sh",
    "s": "s",
    "ra": "a",
}


def _parse_conditions(text: str) -> tuple[list[tuple[str, str, str]], str]:
    """解析筛选条件，返回 (条件列表, 剩余文本)。条件从原文中剔除，剩余部分视为玩家名。"""
    conditions: list[tuple[str, str, str]] = []

    def _repl(match: re.Match) -> str:
        key, op, value = match.group(1), match.group(2), match.group(3).strip("\"'")
        field = _FIELD_MAP.get(key.lower())
        if field:
            conditions.append((field, op, value))
        return " "

    remaining = _CONDITION_PATTERN.sub(_repl, text)
    return conditions, remaining.strip()


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "y", "是", "对"}


def _match_value(operator: str, expected: str, actual) -> bool:
    if operator in (">", ">=", "<", "<=", "=", "!=") and isinstance(actual, (int, float)):
        try:
            expected_num = float(expected)
        except ValueError:
            return False
        if operator == "=":
            return actual == expected_num
        if operator == "!=":
            return actual != expected_num
        if operator == ">":
            return actual > expected_num
        if operator == ">=":
            return actual >= expected_num
        if operator == "<":
            return actual < expected_num
        if operator == "<=":
            return actual <= expected_num
    if operator == "=":
        return str(actual).lower() == expected.lower()
    if operator == "!=":
        return str(actual).lower() != expected.lower()
    if operator == "~":
        return expected.lower() in str(actual).lower()
    if operator == "~=":
        from difflib import SequenceMatcher

        return SequenceMatcher(None, str(actual).lower(), expected.lower()).ratio() >= 0.5
    return False


def _filter_friends(friends: list, conditions: list[tuple[str, str, str]]) -> list:
    result = friends
    for field, op, value in conditions:
        filtered = []
        for f in result:
            stats = f.target.statistics if f.target else None
            if field == "username":
                actual = (f.target.username if f.target else "") or ""
            elif field == "id":
                actual = f.target_id
            elif field == "country":
                actual = (f.target.country_code if f.target else "") or ""
            elif field in ("mutual", "online", "active", "bot", "deleted", "supporter"):
                # 布尔字段：= 与 != 直接比较解析后的布尔值
                if field == "mutual":
                    actual = bool(f.mutual)
                else:
                    actual = bool(f.target and getattr(f.target, f"is_{field}", False))
                expected_bool = _as_bool(value)
                if (op == "=" and actual == expected_bool) or (op == "!=" and actual != expected_bool):
                    filtered.append(f)
                continue
            elif field == "pp":
                actual = stats.pp if stats and stats.pp is not None else 0.0
            elif field == "acc":
                actual = stats.hit_accuracy if stats and stats.hit_accuracy is not None else 0.0
            elif field == "pc":
                actual = stats.play_count if stats else 0
            elif field == "pt":
                actual = stats.play_time if stats else 0
            elif field == "th":
                actual = stats.total_hits if stats else 0
            elif field == "level":
                actual = stats.level.current if stats and stats.level else 0
            elif field == "max_combo":
                actual = stats.maximum_combo if stats else 0
            elif field == "global_rank":
                actual = stats.global_rank if stats and stats.global_rank is not None else 0
            elif field == "ssh":
                actual = stats.grade_counts.ssh if stats and stats.grade_counts else 0
            elif field == "ss":
                actual = stats.grade_counts.ss if stats and stats.grade_counts else 0
            elif field == "sh":
                actual = stats.grade_counts.sh if stats and stats.grade_counts else 0
            elif field == "s":
                actual = stats.grade_counts.s if stats and stats.grade_counts else 0
            elif field == "a":
                actual = stats.grade_counts.a if stats and stats.grade_counts else 0
            else:
                continue
            if _match_value(op, value, actual):
                filtered.append(f)
        result = filtered
    return result
