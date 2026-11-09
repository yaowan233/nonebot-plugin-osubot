import re
import math
from dataclasses import dataclass

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Event, Message
from nonebot_plugin_orm import get_session
from nonebot_plugin_alconna import UniMessage

from ..api import get_server
from ..bindings import find_binding
from ..draw.replay import replay_summary, render_replay_with_core
from ..draw.core_preview import CorePreviewError, read_core_output

replay_analysis = on_command("回放分析", aliases={"回放", "replay", "ra"}, priority=11, block=True)


@dataclass(slots=True)
class ReplayQuery:
    score_id: str | None = None
    user: str | None = None
    bid: str | None = None
    mode: str | None = None
    fmt: str | None = None
    times: str | None = None
    duration: float | None = None
    score_select: str | None = None
    include_fails: bool = False


def parse_replay_query(text: str) -> ReplayQuery:
    """A lone ID is a score; a player plus map ID selects that map's best."""
    query = ReplayQuery()
    text = text.strip().replace("：", ":").replace("＝", "=")
    values: dict[str, str] = {}

    def option(match: re.Match) -> str:
        key, value = match[1].lower(), match[2]
        if key in values:
            raise ValueError(f"参数 {key} 不能重复")
        values[key] = value
        return " "

    text = re.sub(r"(?<!\S)(user|bid|mode|times|duration)=([^\s]+)", option, text, flags=re.I)
    formats = re.findall(r"(?<!\S)\+(png|gif|mp4)(?!\S)", text, flags=re.I)
    if len(formats) > 1:
        raise ValueError("只能选择一种输出格式：+png、+gif 或 +mp4")
    query.fmt = formats[0].lower() if formats else None
    text = re.sub(r"(?<!\S)\+(?:png|gif|mp4)(?!\S)", " ", text, flags=re.I)
    selections = re.findall(r"(?<!\S)(best|recent)(?!\S)", text, flags=re.I)
    if len(selections) > 1:
        raise ValueError("只能选择 best 或 recent")
    query.score_select = selections[0].lower() if selections else None
    text = re.sub(r"(?<!\S)(?:best|recent)(?!\S)", " ", text, flags=re.I)
    query.include_fails = bool(re.search(r"(?<!\S)\+fail(?!\S)", text, flags=re.I))
    text = re.sub(r"(?<!\S)\+fail(?!\S)", " ", text, flags=re.I).strip()
    # Mode suffixes follow the other bot commands, e.g. peppy:m.
    suffix = re.search(r":([\w!]+)\s*$", text)
    if suffix:
        if "mode" in values:
            raise ValueError("模式不能重复指定")
        values["mode"] = suffix[1]
        text = text[: suffix.start()].strip()
    if "mode" in values:
        query.mode = get_server("osu").parse_mode(values["mode"]).key
    query.user = values.get("user")
    query.bid = values.get("bid")
    # Legacy /scores/<mode>/<id> IDs differ from the current unified IDs.
    score_link = re.fullmatch(r"https?://osu\.ppy\.sh/scores/(\d+)/?(?:\?[^\s]*)?", text)
    if score_link:
        query.score_id = score_link[1]
    elif "osu.ppy.sh/scores/" in text:
        raise ValueError("请使用新版成绩链接 https://osu.ppy.sh/scores/<成绩ID>")
    elif text.isdecimal() and query.user is None and query.bid is None:
        query.score_id = text
    elif text:
        player_map = re.fullmatch(r"(.+?)\s+(\d+)", text)
        if player_map:
            if query.user is not None or query.bid is not None:
                raise ValueError("玩家或谱面 ID 不能重复指定")
            query.user, query.bid = player_map[1].strip(), player_map[2]
        elif query.user is None:
            query.user = text
        else:
            raise ValueError("无法识别的回放参数")
    query.times = values.get("times")
    if "duration" in values:
        try:
            query.duration = float(values["duration"])
        except ValueError as error:
            raise ValueError("duration 应为 0 到 30 之间的秒数") from error
    return validate_replay_query(query)


def validate_replay_query(query: ReplayQuery) -> ReplayQuery:
    """Apply the same replay options and limits to commands and agent tools."""
    if query.bid is not None and (not query.bid.isdecimal() or int(query.bid) <= 0):
        raise ValueError("bid 应为正整数谱面 ID")
    if query.score_id is not None:
        if not query.score_id.isdecimal() or int(query.score_id) <= 0:
            raise ValueError("成绩 ID 应为正整数")
        if query.user is not None or query.bid is not None or query.mode or query.score_select or query.include_fails:
            raise ValueError("成绩 ID 查询不能同时指定玩家、谱面、模式、best/recent 或 +fail")
    if query.score_select == "best" and query.bid is None:
        raise ValueError("best 查询需要提供 bid=<谱面ID>")
    selection = query.score_select or ("best" if query.bid else "recent")
    if query.include_fails and selection != "recent":
        raise ValueError("+fail 仅适用于 recent 查询")
    if query.times is not None:
        points = query.times.split("+")
        if len(points) > 4 or (query.fmt == "mp4" and len(points) != 1):
            raise ValueError("最多支持 4 个采样起点，MP4 只能指定一个")
        for point in points:
            if point == "preview":
                continue
            try:
                seconds = float(point)
            except ValueError as error:
                raise ValueError("times 应为非负秒数或 preview，多个起点用 + 分隔") from error
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError("times 应为非负秒数或 preview")
    if query.duration is not None:
        if not math.isfinite(query.duration) or not 0 < query.duration <= 30:
            raise ValueError("duration 应大于 0 且不超过 30 秒")
    if query.fmt in {"gif", "mp4"}:
        query.duration = query.duration or 10
        query.times = query.times or "0"
    elif (query.times is None) != (query.duration is None):
        raise ValueError("截取回放区间需同时提供 times=<起点秒数> 和 duration=<时长秒数>")
    return query


@replay_analysis.handle()
async def _replay(event: Event, arg: Message = CommandArg()):
    try:
        query = parse_replay_query(arg.extract_plain_text())
        if query.score_id is None:
            if query.user is None:
                binding = await find_binding("osu", str(event.get_user_id()), session_factory=get_session)
                if binding is None:
                    await UniMessage.text(
                        "请提供成绩 ID、玩家名，或先用 /bind 绑定账号。发送 /oh 回放 查看用法。"
                    ).finish(reply_to=True)
                query.user = str(binding.osu_id)
                if query.mode is None:
                    query.mode = get_server("osu").parse_mode(str(binding.osu_mode)).key
        preview = await render_replay_with_core(
            score_id=query.score_id,
            user=query.user,
            bid=query.bid,
            mode=query.mode,
            score_select=query.score_select,
            include_fails=query.include_fails,
            fmt=query.fmt,
            times=query.times,
            duration=query.duration,
        )
        raw = read_core_output(preview.path)
    except (ValueError, CorePreviewError) as error:
        await UniMessage.text(f"{error}\n发送 /oh 回放 查看用法。目标成绩需有可访问的回放。").finish(reply_to=True)
    message = UniMessage.text(replay_summary(preview) + "\n")
    if preview.path.suffix.lower() == ".mp4":
        message += UniMessage.video(raw=raw, name=preview.path.name)
    else:
        message += UniMessage.image(raw=raw)
    await message.finish(reply_to=True)
