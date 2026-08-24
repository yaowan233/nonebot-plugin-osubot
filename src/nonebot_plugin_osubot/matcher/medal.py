import re
import json
from html import unescape
from pathlib import Path
from datetime import datetime

from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.internal.adapter import Event, Message
from nonebot.log import logger
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..api import Achievement, fetch_achievements_catalog, get_user_achievements
from ..database import UserData
from ..draw.medal import AchievementRenderRow, draw_achievements
from ..utils import NGM

medal_data_path = Path(__file__).parent.parent / "osufile" / "medals" / "medals.json"
with open(medal_data_path, encoding="utf-8") as file:
    medal_json = json.load(file)

medal = on_command("medal", aliases={"md", "成就"}, priority=11, block=True)
myach = on_command("myach", aliases={"ma", "myachievement", "我的成就"}, priority=11, block=True)
achrec = on_command("achrec", aliases={"ar", "成就推荐", "推荐成就"}, priority=11, block=True)

# 模式名 → osu! API mode 参数
_MODE_MAP = {
    "o": "osu",
    "t": "taiko",
    "c": "fruits",
    "m": "mania",
    "osu": "osu",
    "taiko": "taiko",
    "catch": "fruits",
    "mania": "mania",
}


def _strip_medal_html(text: str) -> str:
    """去除 HTML 标签，并解析 <table> 为纯文本。

    处理 osekai Solution 中常见的 <i>/<b>/<br>/<img>/<solution-note>/<star-rating> 等标签，
    <img> 会被整个移除（不留 src 文字）。
    """
    if not text:
        return ""
    # 移除 <img ...>（含自闭合与成对标签）
    text = re.sub(r"<img[^>]*/?>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # 表格转纯文本
    table_regex = r"<table[^>]*>(.*?)<\/table>"

    def replace_table(table_match: re.Match) -> str:
        table_text = table_match.group(1)
        row_regex = r"<tr[^>]*>(.*?)<\/tr>"
        rows = re.findall(row_regex, table_text, re.DOTALL | re.IGNORECASE)
        result = []
        for row in rows:
            cell_regex = r"<t[hd][^>]*>(.*?)<\/t[hd]>"
            cells = re.findall(cell_regex, row, re.DOTALL | re.IGNORECASE)
            for cell in cells:
                cell_text = re.sub(r"<[^>]*>", "", cell)
                result.append(cell_text)
            result.append("\n")
        return " ".join(result)

    text = re.sub(table_regex, replace_table, text, flags=re.DOTALL | re.IGNORECASE)
    # 移除 <style>/<script>
    text = re.sub(r"<style[^>]*>(.*?)</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>(.*?)</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # <br>/<p>/<div>/<li> 等块级标签转换行
    text = re.sub(r"<(br|/p|/div|/li|/tr|/h\d)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # 其余标签直接删除
    text = re.sub(r"<[^>]+>", "", text)
    # 压缩多余空行
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return unescape(text).strip()


def _get_chinese_solution(name: str) -> str:
    detail = medal_json.get(name) or {}
    return detail.get("MedalSolution", "").strip()


def _filter_achievements_by_mode(achievements: list[dict], mode: str) -> list[dict]:
    """保留通用成就与指定模式的成就。"""
    return [achievement for achievement in achievements if achievement.get("mode") in {None, mode}]


def _get_recommendation_solution(achievement: Achievement) -> str:
    name = achievement.get("name", "")
    if solution := _get_chinese_solution(name):
        return solution
    original = _strip_medal_html(achievement.get("solution") or achievement.get("instructions") or "")
    return f"暂无中文攻略，英文原文：{original}" if original else "暂无可用攻略"


def _pack_urls(achievement: Achievement, local_detail: dict) -> list[str]:
    pack_id = local_detail.get("PackID") or achievement.get("pack_id")
    pack_ids = [value for value in re.split(r",+", str(pack_id)) if value]
    return [f"https://osu.ppy.sh/beatmaps/packs/{value}" for value in pack_ids]


def _related_beatmaps(achievement: Achievement, local_detail: dict) -> list[dict]:
    beatmaps = achievement.get("beatmaps") or []
    if beatmaps:
        return beatmaps[:5]
    beatmap_ids = [value for value in re.split(r",+", local_detail.get("BeatmapID", "")) if value]
    return [{"id": beatmap_id} for beatmap_id in beatmap_ids[:5]]


def _format_achieved_at(value) -> str:
    """格式化成就获得时间（UTC → 本地时间字符串）。"""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d")
    except Exception:
        return str(value)


async def _get_bound_user(qq: str) -> UserData | None:
    """查询 /bind 绑定的用户记录。"""
    async with get_session() as session:
        return await session.scalar(select(UserData).where(UserData.user_id == qq))


async def _get_bound_achievement_request(
    event: Event,
    arg: Message,
    matcher: type[Matcher],
) -> tuple[int, str, list[dict]]:
    user_data = await _get_bound_user(event.get_user_id())
    if not user_data:
        await matcher.finish("该账号尚未绑定，请输入 /bind 用户名 绑定账号")

    uid = user_data.osu_id
    mode_arg = arg.extract_plain_text().strip().lower()
    mode = _MODE_MAP.get(mode_arg, "osu") if mode_arg else NGM.get(str(user_data.osu_mode), "osu")
    try:
        achievements = await get_user_achievements(uid, mode)
    except Exception as e:
        logger.opt(exception=e).error(f"获取成就失败 uid={uid}")
        await matcher.finish(f"获取成就失败：{e}")
    return uid, mode, achievements


async def _render_achievement_rows(
    matcher: type[Matcher],
    *,
    uid: int,
    title: str,
    subtitle: str,
    rows: list[AchievementRenderRow],
) -> bytes:
    try:
        return await draw_achievements(
            {
                "me_name": f"UID {uid}",
                "me_avatar": f"https://a.ppy.sh/{uid}",
                "title": title,
                "subtitle": subtitle,
                "total": len(rows),
                "start": 1,
                "end": len(rows),
                "achievements": rows,
            }
        )
    except Exception as e:
        logger.opt(exception=e).error(f"渲染{title}失败")
        await matcher.finish(f"渲染{title}失败：{e}")


# ===========================================================================
# /md <成就名>：查询单个成就达成方式
# ===========================================================================
@medal.handle()
async def _(msg: Message = CommandArg()):
    name = msg.extract_plain_text().strip()
    if not name:
        await medal.finish("用法：/md <成就名>，例如 /md 500 Combo、/md Rising Star")

    # 优先用本地目录定位（含图标与攻略），无需再请求 osekai 单查接口
    catalog = await fetch_achievements_catalog()
    hit = None
    if catalog:
        name_lower = name.lower()
        hit = next((a for a in catalog if a.get("name", "").lower() == name_lower), None)
        if hit is None:
            hit = next((a for a in catalog if name_lower in a.get("name", "").lower()), None)

    if hit is None:
        await medal.finish("没有找到欸，看看是不是名字打错了")

    # 名称显示与图标
    display_name = hit["name"]
    icon_url = hit.get("icon_url", "") or ""
    grouping = hit.get("grouping", "")

    # 取达成方式：本地中文攻略优先，否则用目录里的 solution/instructions
    words = "获得方式：\n"
    local_detail = medal_json.get(display_name) or {}
    solution = _get_chinese_solution(display_name)
    if not solution:
        solution = hit.get("solution") or hit.get("instructions") or ""
        solution = _strip_medal_html(solution)
    if solution:
        words += solution
    else:
        words += "暂无中文攻略，可在 osu! 网页查看"

    if grouping:
        words = f"分组：{grouping}\n" + words
    if hit.get("mode"):
        mode_names = {"osu": "osu!", "taiko": "osu!taiko", "fruits": "osu!catch", "mania": "osu!mania"}
        words = f"适用模式：{mode_names.get(hit['mode'], hit['mode'])}\n" + words
    if pack_urls := _pack_urls(hit, local_detail):
        words += "\n" + "\n".join(pack_urls)

    msg_out = UniMessage()
    if icon_url:
        msg_out += UniMessage.image(url=icon_url)
    msg_out += UniMessage.text(words.strip())
    await msg_out.send(reply_to=True)

    # 附带相关谱面（最多 5 张，来自目录的 beatmap 建议）
    beatmaps = _related_beatmaps(hit, local_detail)
    if beatmaps:
        beatmap_msg = UniMessage()
        for beatmap in beatmaps:
            title = beatmap.get("SongTitle") or beatmap.get("title") or ""
            diff = beatmap.get("DifficultyName") or beatmap.get("version") or ""
            bmid = beatmap.get("BeatmapID") or beatmap.get("id") or ""
            stars = beatmap.get("Difficulty") or ""
            if title or diff or stars:
                beatmap_msg += f"{title} [{diff}]\n{stars}⭐\n"
            beatmap_msg += f"https://osu.ppy.sh/b/{bmid}\n"
        await beatmap_msg.send()


# ===========================================================================
# /myach [模式]：查询已绑定用户已获得的成就
# ===========================================================================
@myach.handle()
async def _(event: Event, arg: Message = CommandArg()):
    uid, mode, achievements = await _get_bound_achievement_request(event, arg, myach)

    if not achievements:
        await myach.finish("还没有获得任何成就哦，快去创造历史吧！")

    achievements = _filter_achievements_by_mode(achievements, mode)
    if not achievements:
        await myach.finish(f"尚未获得 {mode.upper()} 模式的成就")

    # 排序：获得时间倒序
    achievements.sort(key=lambda a: a.get("achieved_at") or "", reverse=True)

    rows: list[AchievementRenderRow] = [
        {
            "name": a.get("name") or f"成就 {a.get('achievement_id')}",
            "icon": a.get("icon_url")
            or (f"https://assets.ppy.sh/medals/web/{a.get('slug')}.png" if a.get("slug") else ""),
            "grouping": a.get("grouping") or "成就",
            "achieved_at": _format_achieved_at(a.get("achieved_at")),
        }
        for a in achievements
    ]

    img = await _render_achievement_rows(
        myach,
        uid=uid,
        title="已获得成就",
        subtitle=f"共 {len(rows)} 个成就 · {mode.upper()}",
        rows=rows,
    )
    await UniMessage.image(raw=img).finish(reply_to=True)


# ===========================================================================
# /achrec [模式]：根据已获得成就推荐未获得的成就
# ===========================================================================
@achrec.handle()
async def _(event: Event, arg: Message = CommandArg()):
    uid, mode, achievements = await _get_bound_achievement_request(event, arg, achrec)

    # 全量目录
    catalog = await fetch_achievements_catalog()
    if not catalog:
        await achrec.finish("获取成就目录失败，请稍后再试")

    owned_ids = {a.get("achievement_id") for a in achievements if a.get("achievement_id") is not None}

    # 优先本模式，其次全模式；没有中文攻略时保留英文原文。
    mode_ids = [a["id"] for a in catalog if a.get("mode") == mode]
    all_ids = [a["id"] for a in catalog]
    ordered_ids = [i for i in mode_ids if i not in owned_ids] + [
        i for i in all_ids if i not in owned_ids and i not in mode_ids
    ]

    # 取前 15 个推荐
    recommended = [next(a for a in catalog if a["id"] == i) for i in ordered_ids[:15]]
    if not recommended:
        await achrec.finish("太强了！所有成就都获得了，你就是 osu! 传奇！")

    # 组装图片数据 + 文本攻略
    rows: list[AchievementRenderRow] = []
    text_lines = []
    for i, ach in enumerate(recommended, start=1):
        name = ach.get("name", "")
        icon = ach.get("icon_url") or (
            f"https://assets.ppy.sh/medals/web/{ach.get('slug')}.png" if ach.get("slug") else ""
        )
        grouping = ach.get("grouping") or "成就"
        # 中文攻略
        solution = _get_recommendation_solution(ach)
        rows.append(
            {
                "name": name,
                "icon": icon,
                "grouping": grouping,
                "achieved_at": "",
            }
        )
        text_lines.append(f"{i}. {name}（{grouping}）")
        text_lines.append(f"   {solution}")

    img = await _render_achievement_rows(
        achrec,
        uid=uid,
        title="成就推荐",
        subtitle=f"未获得成就推荐 · {mode.upper()} · 已获得 {len(owned_ids)} 个",
        rows=rows,
    )

    # 图片 + 文本攻略
    msg_out = UniMessage.image(raw=img)
    msg_out += UniMessage.text("以下成就你还没有获得，加油：\n" + "\n".join(text_lines))
    await msg_out.finish(reply_to=True)
