from __future__ import annotations

import re
import json
import asyncio
import base64
import datetime
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from pathlib import Path

from langchain.tools import tool
from sqlalchemy import select
from nonebot_plugin_orm import get_session
from nonebot_plugin_alconna import UniMessage

from nonebot_plugin_ai_groupmate.agent import AgentToolBundle, AgentToolContext, register_agent_tool

from .api import get_uid_by_name, get_recommend, get_user_scores, osu_api, safe_async_get
from .draw import draw_bp, draw_info, draw_score, get_score_data, draw_map_info, draw_bmap_info
from .info import get_bg
from .utils import NGM, mods2list
from .file import download_osu
from .mania import generate_preview_pic
from .database import InfoData, UserData, SbUserData
from .exceptions import NetworkError
from .draw.score import cal_score_info
from .draw.rating import draw_rating
from .draw.recommend import draw_recommend
from .draw.echarts import build_bpa_data, draw_bpa_plot, draw_history_plot
from .draw.osu_preview import draw_osu_preview, draw_full_osu_preview
from .draw.match_history import draw_match_history
from .draw.catch_preview import draw_cath_preview
from .draw.taiko_preview import map_to_image, parse_map
from .help_data import get_command_help
from .history_data import merge_osutrack_history

ContentBlock = str | dict[str, Any]
medal_data_path = Path(__file__).parent / "osufile" / "medals" / "medals.json"
with open(medal_data_path, encoding="utf-8") as file:
    medal_json = json.load(file)


@dataclass(slots=True)
class ResolvedOsuUser:
    user_id: int
    name: str
    default_mode: str = "0"
    default_is_lazer: bool = True


def _normalize_source(source: str) -> str:
    source = (source or "osu").strip().lower()
    if source in {"sb", "ppysb"}:
        return "ppysb"
    return "osu"


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if value.lower() in {"none", "null", "nil", "undefined"}:
        return None
    if value in {"我", "自己", "本人", "当前用户", "绑定用户"}:
        return None
    return value


def _clean_user_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() in {"none", "null", "nil", "undefined", "all"}:
        return None
    return value


def _extract_mentioned_user_id(ctx: AgentToolContext) -> str | None:
    if not ctx.event:
        return None

    bot_ids = {
        user_id
        for user_id in (
            _clean_user_id(ctx.bot_id),
            _clean_user_id(getattr(ctx.event, "self_id", None)),
        )
        if user_id
    }
    try:
        message = ctx.event.get_message()
    except Exception:
        return None

    for segment in message:
        segment_type = getattr(segment, "type", None)
        data = getattr(segment, "data", {}) or {}
        if segment_type != "at":
            continue
        target = data.get("qq") or data.get("user_id") or data.get("id") or data.get("target")
        target = _clean_user_id(target)
        if target and target not in bot_ids:
            return target
    return None


def _normalize_mode(mode: str | int | None, source: str) -> str | None:
    if mode is None:
        return None
    mode_text = str(mode).strip()
    if not mode_text or mode_text.lower() in {"none", "null", "nil", "undefined"}:
        return None
    allowed = {"0", "1", "2", "3"}
    if source == "ppysb":
        allowed = {"0", "1", "2", "3", "4", "5", "6", "8"}
    if mode_text not in allowed:
        raise ValueError("mode 必须为 0=std, 1=taiko, 2=ctb/fruits, 3=mania；ppysb 还支持 4/5/6/8")
    return mode_text


def _normalize_range(range_text: str | None, default: str = "1-200") -> tuple[int, int]:
    if not range_text or not range_text.strip():
        range_text = default
    parts = range_text.replace(" ", "").split("-", 1)
    if len(parts) != 2:
        raise ValueError("range 必须是类似 1-20 的格式")
    low, high = int(parts[0]), int(parts[1])
    if not 0 < low < high <= 200:
        raise ValueError("range 只支持 1-200 内的递增范围")
    return low, high


async def _resolve_osu_user(
    ctx: AgentToolContext,
    username: str | None,
    source: str,
    target_user_id: str | int | None = None,
) -> ResolvedOsuUser:
    name = _clean_optional_text(username)
    if name:
        return ResolvedOsuUser(await get_uid_by_name(name, source), name)

    bind_user_id = _clean_user_id(target_user_id) or _extract_mentioned_user_id(ctx) or ctx.user_id
    if not bind_user_id:
        raise ValueError("当前没有可用的用户 ID，请指定 osu 用户名")

    if source == "ppysb":
        async with get_session() as session:
            user = await session.scalar(select(SbUserData).where(SbUserData.user_id == bind_user_id))
        if not user:
            raise ValueError("当前用户尚未绑定 osu 账号，请先使用 /sbbind 用户名")
        return ResolvedOsuUser(user.osu_id, user.osu_name)

    async with get_session() as session:
        user = await session.scalar(select(UserData).where(UserData.user_id == bind_user_id))

    if not user:
        raise ValueError("当前用户尚未绑定 osu 账号，请先使用 /bind 用户名")

    return ResolvedOsuUser(
        user.osu_id,
        user.osu_name,
        default_mode=str(user.osu_mode),
        default_is_lazer=True if user.lazer_mode is None else user.lazer_mode,
    )


def _resolve_mode(mode: str | int | None, user: ResolvedOsuUser, source: str) -> str:
    return _normalize_mode(mode, source) or _normalize_mode(user.default_mode, source) or "0"


def _resolve_is_lazer(is_lazer: bool | None, user: ResolvedOsuUser) -> bool:
    return user.default_is_lazer if is_lazer is None else is_lazer


async def _send_image(ctx: AgentToolContext, raw: bytes | BytesIO) -> str:
    await UniMessage.image(raw=raw).send(target=ctx.send_target)
    return "已发送图片"


def _to_bytes(raw: bytes | BytesIO) -> bytes:
    if isinstance(raw, BytesIO):
        return raw.getvalue()
    return raw


def _image_tool_result(text: str, raw: bytes | BytesIO, include_image: bool) -> str | list[ContentBlock]:
    if not include_image:
        return text
    image_data = base64.b64encode(_to_bytes(raw)).decode("utf-8")
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
    ]


def _strip_medal_html(text: str) -> str:
    table_match = re.search(r"<table[^>]*>(.*?)</table>", text, re.DOTALL)
    if table_match:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.DOTALL)
        result = ""
        for row in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
            result += " ".join(re.sub(r"<[^>]*>", "", cell) for cell in cells) + "\n"
        text = re.sub(r"<table[^>]*>.*?</table>", result, text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    return re.sub(r"<[^>]+>", "", text)


async def _draw_preview(map_id: str, mode: str, mods: str, full: bool) -> tuple[bytes | BytesIO | Path, str | None]:
    if not map_id.isdigit():
        raise ValueError("map_id 必须是数字")
    if mode not in {"0", "1", "2", "3"}:
        raise ValueError("preview 仅支持 0=std, 1=taiko, 2=ctb/fruits, 3=mania")
    data = await osu_api("map", map_id=int(map_id))
    beatmapset_id = data["beatmapset_id"]
    mod_list = mods2list(mods) if mods else []

    if "GIF" in "".join(mod.upper() for mod in mod_list):
        media = (
            await draw_full_osu_preview(int(map_id), beatmapset_id)
            if full
            else await draw_osu_preview(int(map_id), beatmapset_id)
        )
        extra_text = (
            f"点击预览：\nhttps://beatmap.try-z.net/?b={map_id}\nhttps://beatmap.try-z.net/dev/?b={map_id}"
            if mode == "0"
            else None
        )
        return media, extra_text
    if mode == "3":
        osu = await download_osu(beatmapset_id, int(map_id))
        return await generate_preview_pic(osu, full), None
    if mode == "2":
        return await draw_cath_preview(int(map_id), beatmapset_id, mod_list), None
    if mode == "1":
        osu = await download_osu(beatmapset_id, int(map_id))
        return map_to_image(parse_map(osu)), None
    image = await draw_osu_preview(int(map_id), beatmapset_id)
    return image, f"点击预览：\nhttps://beatmap.try-z.net/?b={map_id}\nhttps://beatmap.try-z.net/dev/?b={map_id}"


@register_agent_tool
def build_osu_agent_tools(ctx: AgentToolContext) -> AgentToolBundle:
    @tool("get_osubot_command_help")
    async def get_osubot_command_help(topic: str = "overview") -> str:
        """
        查询 OSUBot 的手动聊天指令、格式、简称和示例，不执行成绩查询。
        topic 可用 overview、bind、mode、score、map、profile、game、sb、all，也可传中文主题。
        """
        return get_command_help(topic)

    @tool("send_osu_user_info")
    async def send_osu_user_info(
        username: str | None = None,
        target_user_id: str | None = None,
        mode: str | None = None,
        day: int = 0,
        source: str = "osu",
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送 osu 玩家信息图。
        username 不填时使用当前用户或被 @ 群友绑定的 osu 账号。
        mode: 0=std, 1=taiko, 2=ctb/fruits, 3=mania。source: osu 或 ppysb。
        """
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            data = await draw_info(user.user_id, NGM[mode], max(day, 0), source)
            await _send_image(ctx, data)
            return _image_tool_result(
                f"已发送 {user.name} 的 osu 信息图。图片中包含玩家资料、排名、pp、acc 等信息。",
                data,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询 osu 玩家信息失败: {e}"
        except Exception as e:
            return f"发送 osu 玩家信息失败: {e}"

    @tool("send_osu_bp")
    async def send_osu_bp(
        username: str | None = None,
        target_user_id: str | None = None,
        best: int = 1,
        mode: str | None = None,
        mods: str = "",
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送 osu 玩家指定 bp 成绩图。best 为 bp 序号，范围 1-200；mods 可填 HDHR、DT、HD 等。
        """
        try:
            if best < 1 or best > 200:
                return "best 必须在 1-200 之间"
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer, user)
            data = await draw_score(
                "bp",
                user.user_id,
                is_lazer,
                NGM[mode],
                mods2list(mods) if mods else [],
                [],
                source,
                best=best,
            )
            await _send_image(ctx, data)
            return _image_tool_result(
                f"已发送 {user.name} 的 bp{best}。图片中包含成绩、pp、acc、combo、miss、mods、谱面等信息。",
                data,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询 bp 失败: {e}"
        except Exception as e:
            return f"发送 bp 失败: {e}"

    @tool("send_osu_bp_list")
    async def send_osu_bp_list(
        username: str | None = None,
        target_user_id: str | None = None,
        range_text: str = "1-30",
        mode: str | None = None,
        mods: str = "",
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送 osu 玩家 bp 列表图。range_text 为范围，例如 1-20、20-50，最大到 200。
        """
        try:
            source = _normalize_source(source)
            low, high = _normalize_range(range_text, default="1-30")
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer, user)
            data = await draw_bp(
                "bp",
                user.user_id,
                is_lazer,
                NGM[mode],
                mods2list(mods) if mods else [],
                low,
                high,
                0,
                [],
                source,
            )
            await _send_image(ctx, data)
            return _image_tool_result(
                f"已发送 {user.name} 的 bp{low}-{high}。图片中包含 bp 列表，可用于分析成绩分布和整体表现。",
                data,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询 bp 列表失败: {e}"
        except Exception as e:
            return f"发送 bp 列表失败: {e}"

    @tool("send_osu_recent_or_pr")
    async def send_osu_recent_or_pr(
        username: str | None = None,
        target_user_id: str | None = None,
        kind: str = "recent",
        index: int = 1,
        mode: str | None = None,
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送最近成绩或最近 best 成绩图。kind 为 recent 或 pr；index 表示第几条，默认 1。
        """
        try:
            if index < 1:
                return "index 必须大于等于 1"
            score_type = "pr" if kind.lower() == "pr" else "recent"
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer, user)
            data = await draw_score(score_type, user.user_id, is_lazer, NGM[mode], [], [], source, index)
            await _send_image(ctx, data)
            label = "最近 best" if score_type == "pr" else "最近"
            return _image_tool_result(
                f"已发送 {user.name} 的第 {index} 个{label}成绩。"
                "图片中包含成绩、pp、acc、combo、miss、mods、谱面等信息。",
                data,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询最近成绩失败: {e}"
        except Exception as e:
            return f"发送最近成绩失败: {e}"

    @tool("send_osu_score")
    async def send_osu_score(
        beatmap_id: str,
        username: str | None = None,
        target_user_id: str | None = None,
        mode: str | None = None,
        mods: str = "",
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """
        查询并发送玩家在指定 beatmap 上的成绩图。beatmap_id 是谱面 ID。
        """
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer, user)
            data = await get_score_data(
                user.user_id,
                is_lazer,
                NGM[mode],
                mods2list(mods) if mods else [],
                int(beatmap_id),
                source,
            )
            await _send_image(ctx, data)
            return _image_tool_result(
                f"已发送 {user.name} 在谱面 {beatmap_id} 上的成绩。图片中包含成绩、pp、acc、combo、miss、mods 等信息。",
                data,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询谱面成绩失败: {e}"
        except Exception as e:
            return f"发送谱面成绩失败: {e}"

    @tool("send_osu_history")
    async def send_osu_history(
        username: str | None = None,
        target_user_id: str | None = None,
        mode: str | None = None,
        day: int = 0,
        source: str = "osu",
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送玩家 pp/rank 历史曲线图。day 为查询最近多少天，0 表示全部。"""
        try:
            source = _normalize_source(source)
            if source != "osu":
                return "history 暂仅支持 osu 官方服务器"
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            query = select(InfoData).where(InfoData.osu_id == user.user_id, InfoData.osu_mode == int(mode))
            if day > 0:
                query = query.where(InfoData.date >= datetime.date.today() - datetime.timedelta(days=day))
            query = query.order_by(InfoData.date)
            async with get_session() as session:
                data = (await session.scalars(query)).all()

            local_points = [
                (item.pp, str(item.date), item.g_rank) for item in data if item.g_rank is not None and item.g_rank != 0
            ]
            has_local_points = bool(local_points)
            points, used_osutrack = await merge_osutrack_history(user.user_id, int(mode), local_points, day)
            if not points:
                return f"没有找到 {user.name} 的历史数据"
            pp_ls, date_ls, rank_ls = map(list, zip(*points))
            source_label = "本地记录"
            if used_osutrack:
                source_label = "本地记录 + osu!track" if has_local_points else "osu!track"
            image = await draw_history_plot(
                pp_ls,
                date_ls,
                rank_ls,
                f"{user.name} {NGM[mode]} pp/rank history",
                username=user.name,
                mode=NGM[mode],
                user_id=user.user_id,
                source_label=source_label,
            )
            await _send_image(ctx, image)
            return _image_tool_result(
                f"已发送 {user.name} 的 {NGM[mode]} pp/rank 历史曲线图。",
                image,
                include_image_for_analysis,
            )
        except Exception as e:
            return f"发送历史曲线失败: {e}"

    @tool("send_osu_bp_analysis")
    async def send_osu_bp_analysis(
        username: str | None = None,
        target_user_id: str | None = None,
        mode: str | None = None,
        source: str = "osu",
        is_lazer: bool | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送玩家 bp 分析图，展示 bp 长度、mod 贡献和 mapper 贡献。"""
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            mode = _resolve_mode(mode, user, source)
            is_lazer = _resolve_is_lazer(is_lazer, user)
            score_ls = await get_user_scores(user.user_id, NGM[mode], "best", source, legacy_only=not is_lazer)
            if not score_ls:
                return f"没有找到 {user.name} 的 bp 成绩"

            for score in score_ls:
                if not is_lazer or source == "ppysb":
                    score.mods = [mod for mod in score.mods if mod.acronym != "CL"]
                for mod in score.mods:
                    if not score.beatmap:
                        continue
                    if mod.acronym in {"DT", "NC"}:
                        setattr(score.beatmap, "total_length", score.beatmap.total_length / 1.5)
                    if mod.acronym == "HT":
                        setattr(score.beatmap, "total_length", score.beatmap.total_length / 0.75)

            score_ls = [cal_score_info(is_lazer, score) for score in score_ls]
            data = await build_bpa_data(score_ls, source)
            image = await draw_bpa_plot(
                f"{user.name} {NGM[mode]} 模式",
                username=user.name,
                mode=NGM[mode],
                user_id=user.user_id,
                source=source,
                **data,
            )
            await _send_image(ctx, image)
            return _image_tool_result(
                f"已发送 {user.name} 的 {NGM[mode]} bp 分析图。",
                image,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询 bp 分析失败: {e}"
        except Exception as e:
            return f"发送 bp 分析失败: {e}"

    @tool("send_osu_recommend")
    async def send_osu_recommend(
        username: str | None = None,
        target_user_id: str | None = None,
        mode: str | None = None,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送推荐谱面图。"""
        try:
            user = await _resolve_osu_user(ctx, username, "osu", target_user_id)
            mode = _resolve_mode(mode, user, "osu")
            api_task = asyncio.create_task(get_recommend(user.user_id, mode))
            done, _ = await asyncio.wait([api_task], timeout=5)
            if not done:
                await UniMessage.text("正在获取推荐谱面，请稍候...").send(target=ctx.send_target)
            recommend_data = await api_task
            if not recommend_data.recommendations:
                return "暂时没有找到可推荐的谱面，已加入更新队列，请明天再来查看推荐吧"
            image = await draw_recommend(recommend_data, user.name, f"https://a.ppy.sh/{user.user_id}")
            await _send_image(ctx, image)
            return _image_tool_result(
                f"已发送 {user.name} 的推荐谱面图。",
                image,
                include_image_for_analysis,
            )
        except NetworkError as e:
            return f"查询推荐谱面失败: {e}"
        except Exception as e:
            return f"发送推荐谱面失败: {e}"

    @tool("send_osu_profile_url")
    async def send_osu_profile_url(
        username: str | None = None,
        target_user_id: str | None = None,
        source: str = "osu",
    ) -> str:
        """发送玩家 osu 主页链接。"""
        try:
            source = _normalize_source(source)
            user = await _resolve_osu_user(ctx, username, source, target_user_id)
            url = f"https://osu.ppy.sh/u/{user.user_id}" if source == "osu" else f"https://akatsuki.gg/u/{user.user_id}"
            await UniMessage.text(url).send(target=ctx.send_target)
            return f"已发送 {user.name} 的主页链接: {url}"
        except Exception as e:
            return f"发送主页链接失败: {e}"

    @tool("send_osu_match_history")
    async def send_osu_match_history(
        match_id: str,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送 osu match 对局历史图。match_id 为多人房间 ID。"""
        try:
            image = await draw_match_history(match_id.strip())
            await _send_image(ctx, image)
            return _image_tool_result(
                f"已发送 match {match_id} 对局历史图。",
                image,
                include_image_for_analysis,
            )
        except Exception as e:
            return f"发送 match 历史失败: {e}"

    @tool("send_osu_match_rating")
    async def send_osu_match_rating(
        match_id: str,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送 osu match rating 图。match_id 为多人房间 ID。"""
        try:
            image = await draw_rating(match_id.strip())
            await _send_image(ctx, image)
            return _image_tool_result(
                f"已发送 match {match_id} rating 图。",
                image,
                include_image_for_analysis,
            )
        except Exception as e:
            return f"发送 match rating 失败: {e}"

    @tool("send_osu_preview")
    async def send_osu_preview(
        map_id: str,
        mode: str | None = "0",
        mods: str = "",
        full: bool = False,
        include_image_for_analysis: bool = False,
    ) -> str | list[ContentBlock]:
        """查询并发送 beatmap 预览图。mode: 0=std, 1=taiko, 2=ctb/fruits, 3=mania。"""
        try:
            mode = _normalize_mode(mode, "osu") or "0"
            media, extra_text = await _draw_preview(map_id, mode, mods, full)
            if isinstance(media, Path):
                message = UniMessage.video(raw=media.read_bytes(), name=media.name)
            else:
                message = UniMessage.image(raw=media)
            if extra_text:
                message += UniMessage.text("\n" + extra_text)
            await message.send(target=ctx.send_target)
            text = f"已发送谱面 {map_id} 的 {NGM[mode]} {'完整预览视频' if isinstance(media, Path) else '预览图'}。"
            if extra_text:
                text += "\n" + extra_text
            if isinstance(media, Path):
                return text
            return _image_tool_result(text, media, include_image_for_analysis)
        except NetworkError as e:
            return f"查询谱面预览失败: {e}"
        except Exception as e:
            return f"发送谱面预览失败: {e}"

    @tool("send_osu_background")
    async def send_osu_background(map_id: str, include_image_for_analysis: bool = False) -> str | list[ContentBlock]:
        """提取并发送 beatmap 背景图。map_id 为谱面 ID。"""
        try:
            image = await get_bg(map_id.strip())
            raw = BytesIO()
            image.convert("RGB").save(raw, "jpeg")
            await _send_image(ctx, raw)
            return _image_tool_result(f"已发送谱面 {map_id} 的背景图。", raw, include_image_for_analysis)
        except NetworkError as e:
            return f"获取谱面背景失败: {e}"
        except Exception as e:
            return f"发送谱面背景失败: {e}"

    @tool("send_osu_medal")
    async def send_osu_medal(name: str) -> str:
        """查询并发送 osu medal/成就获得方式。name 为 medal 名称。"""
        try:
            response = await safe_async_get(f"https://osekai.net/medals/api/public/get_medal.php?medal={name}")
            medal_data = response.json()
            if "MedalID" not in medal_data:
                return "没有找到这个 medal，可能是名字写错了"

            words = ""
            if medal_data["Restriction"] != "NULL":
                words += f"限制模式：{medal_data['Restriction']}\n"
            words += "获得方式：\n"
            if medal_data["Name"] in medal_json:
                words += medal_json[medal_data["Name"]]["MedalSolution"]
            else:
                words += medal_data["Solution"] or medal_data["Instructions"]
                words = _strip_medal_html(words)
            if medal_data["PackID"]:
                words += f"\nhttps://osu.ppy.sh/beatmaps/packs/{medal_data['PackID'].rstrip(',,,')}"

            await (UniMessage.image(url=medal_data["Link"]) + words).send(target=ctx.send_target)
            beatmaps = medal_data.get("beatmaps") or []
            if beatmaps:
                msg = UniMessage()
                for beatmap in beatmaps[:5]:
                    msg += (
                        f"{beatmap['SongTitle']} [{beatmap['DifficultyName']}]\n"
                        f"{beatmap['Difficulty']}⭐\nhttps://osu.ppy.sh/b/{beatmap['BeatmapID']}\n"
                    )
                await msg.send(target=ctx.send_target)
            return f"已发送 medal {medal_data['Name']} 的获得方式。\n{words}"
        except Exception as e:
            return f"查询 medal 失败: {e}"

    @tool("send_osu_map_info")
    async def send_osu_map_info(map_id: str, mods: str = "") -> str:
        """
        查询并发送 osu beatmap 信息图。map_id 是单张谱面 ID；mods 可填 HDHR、DT 等。
        """
        try:
            data = await draw_map_info(int(map_id), mods2list(mods) if mods else [])
            await _send_image(ctx, data)
            return f"已发送谱面 {map_id} 信息图"
        except NetworkError as e:
            return f"查询谱面失败: {e}"
        except Exception as e:
            return f"发送谱面信息失败: {e}"

    @tool("send_osu_beatmapset_info")
    async def send_osu_beatmapset_info(set_id: str) -> str:
        """
        查询并发送 osu beatmapset 信息图。set_id 是谱面集 ID。
        """
        try:
            data = await draw_bmap_info(set_id)
            await _send_image(ctx, data)
            return f"已发送 beatmapset {set_id} 信息图"
        except NetworkError as e:
            return f"查询 beatmapset 失败: {e}"
        except Exception as e:
            return f"发送 beatmapset 信息失败: {e}"

    return AgentToolBundle(
        tools=[
            get_osubot_command_help,
            send_osu_user_info,
            send_osu_bp,
            send_osu_bp_list,
            send_osu_recent_or_pr,
            send_osu_score,
            send_osu_history,
            send_osu_bp_analysis,
            send_osu_recommend,
            send_osu_profile_url,
            send_osu_match_history,
            send_osu_match_rating,
            send_osu_preview,
            send_osu_background,
            send_osu_medal,
            send_osu_map_info,
            send_osu_beatmapset_info,
        ],
        instructions=[
            "- 用户询问“怎么用/什么指令/有哪些命令/格式或简称”时，调用 get_osubot_command_help，"
            "根据问题选择 topic，并原样保留工具返回的斜杠指令和示例。",
            "- 区分教学和执行：例如“BP 指令怎么用”只查 command help；“帮我查 BP”才调用成绩工具。"
            "不要为了演示用法而调用会发图或执行查询的工具。",
            "- 未指定玩家、用户说“我/自己/我的”时，不要传 username；工具会使用当前发言用户绑定的 osu 账号。",
            "- 用户想查被 @ 的群友时，不要传 username；工具会自动读取消息中的非 bot @ 目标并使用该群友绑定账号。",
            "- 用户明确给出群友 QQ/user_id 时，传 target_user_id；这会查询该群友绑定的 osu 账号。",
            "- 未指定模式时，不要传 mode；工具会使用绑定账号的默认模式。未指定 lazer/stable 时，不要传 is_lazer。",
            "- 如果用户只要求查询/发图，不要传 include_image_for_analysis，发图后调用 finish 或简短结束。",
            "- 如果用户问“打得怎么样/发挥如何/分析/评价/看看问题”，传 include_image_for_analysis=true；"
            "看到工具返回的图片后，再基于图片内容给出简短评价。",
            "- send_osu_user_info: 用户想查 osu 玩家资料、info、个人信息图时使用。",
            "- send_osu_bp: 用户想查某个 bp 序号、最好成绩、bp1/bp10 时使用。",
            "- send_osu_bp_list: 用户想实际查询 bp 列表、bl/bplist/pfm 或一段 bp 范围时使用。默认范围优先用 1-30。",
            "- send_osu_recent_or_pr: 用户想实际查询 recent/re 或 pr/最近通过的单条成绩时使用。",
            "- send_osu_score: 用户想查某人在指定谱面上的成绩时使用。",
            "- send_osu_history: 用户想查 pp/rank 历史、history、最近一段时间变化曲线时使用。",
            "- send_osu_bp_analysis: 用户想查 bp 分析、bpa、bp 构成、mod/mapper/长度贡献时使用。",
            "- send_osu_recommend: 用户想要推荐谱面、推荐铺面、recommend 时使用。",
            "- send_osu_profile_url: 用户想要 osu 主页链接、个人主页、mu 时使用。",
            "- send_osu_match_history: 用户想查 match/multiplayer 对局历史图时使用。",
            "- send_osu_match_rating: 用户想查 match rating、多人房评分图时使用。",
            "- send_osu_preview: 用户想看谱面预览、preview、完整预览时使用。",
            "- send_osu_background: 用户想提取谱面背景、bg/getbg、背景图时使用。",
            "- send_osu_medal: 用户想查 medal/成就获得方式时使用。",
            "- send_osu_map_info: 用户想实际查询单张谱面 m/map/beatmap 信息时使用。",
            "- send_osu_beatmapset_info: 用户想实际查询谱面集 bm/bmap/beatmapset 信息时使用。",
        ],
    )
