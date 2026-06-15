from __future__ import annotations

from langchain.tools import tool
from sqlalchemy import select
from nonebot_plugin_orm import get_session
from nonebot_plugin_alconna import UniMessage

from nonebot_plugin_ai_groupmate.agent import AgentToolBundle, AgentToolContext, register_agent_tool

from .api import get_uid_by_name
from .draw import draw_bp, draw_info, draw_score, get_score_data, draw_map_info, draw_bmap_info
from .utils import NGM, mods2list
from .database import UserData, SbUserData
from .exceptions import NetworkError


def _normalize_source(source: str) -> str:
    source = (source or "osu").strip().lower()
    if source in {"sb", "ppysb"}:
        return "ppysb"
    return "osu"


def _normalize_mode(mode: str | int, source: str) -> str:
    mode_text = str(mode).strip()
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


async def _resolve_osu_user(ctx: AgentToolContext, username: str | None, source: str) -> tuple[int, str]:
    if username and username.strip():
        name = username.strip()
        return await get_uid_by_name(name, source), name

    if not ctx.user_id:
        raise ValueError("当前没有可用的用户 ID，请指定 osu 用户名")

    model = SbUserData if source == "ppysb" else UserData
    async with get_session() as session:
        user = await session.scalar(select(model).where(model.user_id == ctx.user_id))

    if not user:
        bind_command = "/sbbind" if source == "ppysb" else "/bind"
        raise ValueError(f"当前用户尚未绑定 osu 账号，请先使用 {bind_command} 用户名")

    return user.osu_id, user.osu_name


async def _send_image(ctx: AgentToolContext, raw: bytes) -> str:
    await UniMessage.image(raw=raw).send(target=ctx.send_target)
    return "已发送图片"


@register_agent_tool
def build_osu_agent_tools(ctx: AgentToolContext) -> AgentToolBundle:
    @tool("send_osu_user_info")
    async def send_osu_user_info(
        username: str | None = None,
        mode: str = "0",
        day: int = 0,
        source: str = "osu",
    ) -> str:
        """
        查询并发送 osu 玩家信息图。
        username 不填时使用当前用户绑定的 osu 账号。
        mode: 0=std, 1=taiko, 2=ctb/fruits, 3=mania。source: osu 或 ppysb。
        """
        try:
            source = _normalize_source(source)
            mode = _normalize_mode(mode, source)
            user_id, name = await _resolve_osu_user(ctx, username, source)
            data = await draw_info(user_id, NGM[mode], max(day, 0), source)
            await _send_image(ctx, data)
            return f"已发送 {name} 的 osu 信息图"
        except NetworkError as e:
            return f"查询 osu 玩家信息失败: {e}"
        except Exception as e:
            return f"发送 osu 玩家信息失败: {e}"

    @tool("send_osu_bp")
    async def send_osu_bp(
        username: str | None = None,
        best: int = 1,
        mode: str = "0",
        mods: str = "",
        source: str = "osu",
        is_lazer: bool = True,
    ) -> str:
        """
        查询并发送 osu 玩家指定 bp 成绩图。best 为 bp 序号，范围 1-200；mods 可填 HDHR、DT、HD 等。
        """
        try:
            if best < 1 or best > 200:
                return "best 必须在 1-200 之间"
            source = _normalize_source(source)
            mode = _normalize_mode(mode, source)
            user_id, name = await _resolve_osu_user(ctx, username, source)
            data = await draw_score(
                "bp",
                user_id,
                is_lazer,
                NGM[mode],
                mods2list(mods) if mods else [],
                [],
                source,
                best=best,
            )
            await _send_image(ctx, data)
            return f"已发送 {name} 的 bp{best}"
        except NetworkError as e:
            return f"查询 bp 失败: {e}"
        except Exception as e:
            return f"发送 bp 失败: {e}"

    @tool("send_osu_bp_list")
    async def send_osu_bp_list(
        username: str | None = None,
        range_text: str = "1-20",
        mode: str = "0",
        mods: str = "",
        source: str = "osu",
        is_lazer: bool = True,
    ) -> str:
        """
        查询并发送 osu 玩家 bp 列表图。range_text 为范围，例如 1-20、20-50，最大到 200。
        """
        try:
            source = _normalize_source(source)
            mode = _normalize_mode(mode, source)
            low, high = _normalize_range(range_text, default="1-20")
            user_id, name = await _resolve_osu_user(ctx, username, source)
            data = await draw_bp(
                "bp",
                user_id,
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
            return f"已发送 {name} 的 bp{low}-{high}"
        except NetworkError as e:
            return f"查询 bp 列表失败: {e}"
        except Exception as e:
            return f"发送 bp 列表失败: {e}"

    @tool("send_osu_recent_or_pr")
    async def send_osu_recent_or_pr(
        username: str | None = None,
        kind: str = "recent",
        index: int = 1,
        mode: str = "0",
        source: str = "osu",
        is_lazer: bool = True,
    ) -> str:
        """
        查询并发送最近成绩或最近 best 成绩图。kind 为 recent 或 pr；index 表示第几条，默认 1。
        """
        try:
            if index < 1:
                return "index 必须大于等于 1"
            score_type = "pr" if kind.lower() == "pr" else "recent"
            source = _normalize_source(source)
            mode = _normalize_mode(mode, source)
            user_id, name = await _resolve_osu_user(ctx, username, source)
            data = await draw_score(score_type, user_id, is_lazer, NGM[mode], [], [], source, index)
            await _send_image(ctx, data)
            label = "最近 best" if score_type == "pr" else "最近"
            return f"已发送 {name} 的第 {index} 个{label}成绩"
        except NetworkError as e:
            return f"查询最近成绩失败: {e}"
        except Exception as e:
            return f"发送最近成绩失败: {e}"

    @tool("send_osu_score")
    async def send_osu_score(
        beatmap_id: str,
        username: str | None = None,
        mode: str = "0",
        mods: str = "",
        source: str = "osu",
        is_lazer: bool = True,
    ) -> str:
        """
        查询并发送玩家在指定 beatmap 上的成绩图。beatmap_id 是谱面 ID。
        """
        try:
            source = _normalize_source(source)
            mode = _normalize_mode(mode, source)
            user_id, name = await _resolve_osu_user(ctx, username, source)
            data = await get_score_data(
                user_id,
                is_lazer,
                NGM[mode],
                mods2list(mods) if mods else [],
                beatmap_id,
                source,
            )
            await _send_image(ctx, data)
            return f"已发送 {name} 在谱面 {beatmap_id} 上的成绩"
        except NetworkError as e:
            return f"查询谱面成绩失败: {e}"
        except Exception as e:
            return f"发送谱面成绩失败: {e}"

    @tool("send_osu_map_info")
    async def send_osu_map_info(map_id: str, mods: str = "") -> str:
        """
        查询并发送 osu beatmap 信息图。map_id 是单张谱面 ID；mods 可填 HDHR、DT 等。
        """
        try:
            data = await draw_map_info(map_id, mods2list(mods) if mods else [])
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
            send_osu_user_info,
            send_osu_bp,
            send_osu_bp_list,
            send_osu_recent_or_pr,
            send_osu_score,
            send_osu_map_info,
            send_osu_beatmapset_info,
        ],
        instructions=[
            "- send_osu_user_info: 用户想查 osu 玩家资料、info、个人信息图时使用。",
            "- send_osu_bp: 用户想查某个 bp 序号、最好成绩、bp1/bp10 时使用。",
            "- send_osu_bp_list: 用户想查 bp 列表、bplist、pfm 或一段 bp 范围时使用。",
            "- send_osu_recent_or_pr: 用户想查 recent/re 或 pr/最近 best 成绩时使用。",
            "- send_osu_score: 用户想查某人在指定谱面上的成绩时使用。",
            "- send_osu_map_info: 用户想查单张谱面 map/beatmap 信息时使用。",
            "- send_osu_beatmapset_info: 用户想查谱面集 beatmapset/bmap 信息时使用。",
        ],
    )
