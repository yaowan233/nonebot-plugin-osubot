import math

from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM, normalize_map_mode
from ..api import osu_api
from .utils import split_msg
from .map_context import get_last_map_id, remember_map_and_set
from ..exceptions import NetworkError
from ..draw.osu_preview import draw_osu_preview, draw_full_osu_preview, render_preview

video_preview_commands = {"视频预览", "完整视频", "vpreview", "vp"}
generate_preview = on_command(
    "预览",
    aliases={"preview", "完整预览", *video_preview_commands},
    priority=11,
    block=True,
)


def is_gif_preview(state: T_State) -> bool:
    return "GIF" in "".join(mod.upper() for mod in state["mods"])


def format_estimated_time(seconds: float) -> str:
    rounded_seconds = max(10, math.ceil(seconds / 10) * 10)
    minutes, remaining_seconds = divmod(rounded_seconds, 60)
    if not minutes:
        return f"{remaining_seconds}秒"
    if not remaining_seconds:
        return f"{minutes}分钟"
    return f"{minutes}分{remaining_seconds}秒"


@generate_preview.handle(parameterless=[split_msg()])
async def _(event: Event, state: T_State):
    osu_id = state["target"] or get_last_map_id(event)
    if not osu_id or not osu_id.isdigit():
        await UniMessage.text("请输入正确的地图mapID，或先查询一张谱面").finish(reply_to=True)
    try:
        data = await osu_api("map", map_id=int(osu_id))
    except NetworkError as e:
        await UniMessage.text(f"查找map_id:{osu_id} 信息时 {str(e)}").finish(reply_to=True)
    remember_map_and_set(event, osu_id, data["beatmapset_id"])
    if not (0 <= int(state["mode"]) <= 3):
        await UniMessage.text("模式应为0-3！\n0: std\n1:taiko\n2:ctb\n3: mania").finish()
    state["mode"] = normalize_map_mode(state["mode"], int(data["mode_int"]))

    command = state["_prefix"]["command"][0]
    is_video_command = command in video_preview_commands
    want_gif = is_gif_preview(state)
    is_full = command == "完整预览" or is_video_command
    mode_int = int(state["mode"])

    # ------------------------------------------------------------------
    # 完整视频：视频命令 / 完整预览（无论是否带 +GIF），所有模式统一 mp4。
    # 【行为变更】旧代码里 "完整预览"(不带+GIF) 的 std 分支只发 10s gif、
    # mania 发整张静态图；现在统一为完整 mp4。如需恢复旧行为，把这里改成
    # 按 mode 分支调用 render_preview(fmt="png"/"gif") 即可。
    # ------------------------------------------------------------------
    if is_full:
        # core 链路没有分片进度，开头先发一句固定提示（A 决策）；
        # 若回退到旧链路，send_estimate 仍会在采样后补发预计时间。
        await UniMessage.text("正在生成完整预览，请稍候…").send(reply_to=True)

        async def send_estimate(seconds: float) -> None:
            if seconds < 15:
                return
            estimate = format_estimated_time(seconds)
            await UniMessage.text(f"正在生成完整预览，预计还需约{estimate}，请稍候…").send(reply_to=True)

        video = await draw_full_osu_preview(
            int(osu_id),
            data["beatmapset_id"],
            progress_callback=send_estimate,
            target_mode=mode_int,
            mods=state["mods"],
        )
        msg = UniMessage.video(raw=video.read_bytes(), name=video.name)
        if state["mode"] == "0":
            msg += UniMessage.text(
                f"点击预览：\nhttps://beatmap.try-z.net/?b={osu_id}\nhttps://beatmap.try-z.net/dev/?b={osu_id}"
            )
        await msg.finish(reply_to=False)

    # ------------------------------------------------------------------
    # GIF 预览（+GIF，非完整）：任意模式 -> binary --fmt=gif --convert=...
    # ------------------------------------------------------------------
    if want_gif:
        pic = await draw_osu_preview(
            int(osu_id),
            data["beatmapset_id"],
            False,
            target_mode=mode_int,
            mods=state["mods"],
        )
        msg = UniMessage.image(raw=pic)
        if state["mode"] == "0":
            msg += UniMessage.text(
                f"点击预览：\nhttps://beatmap.try-z.net/?b={osu_id}\nhttps://beatmap.try-z.net/dev/?b={osu_id}"
            )
        await msg.finish(reply_to=True)

    # ------------------------------------------------------------------
    # 静态预览：std -> gif（保持旧 UX）；taiko/ctb/mania -> png
    # ------------------------------------------------------------------
    if state["mode"] == "0":
        pic = await render_preview(
            int(osu_id), data["beatmapset_id"], 0, fmt="gif", mods=state["mods"]
        )
        msg = UniMessage.image(raw=pic) + UniMessage.text(
            f"点击预览：\nhttps://beatmap.try-z.net/?b={osu_id}\nhttps://beatmap.try-z.net/dev/?b={osu_id}"
        )
        await msg.finish(reply_to=True)
    elif state["mode"] in ("1", "2", "3"):
        pic = await render_preview(
            int(osu_id), data["beatmapset_id"], mode_int, fmt="png", mods=state["mods"]
        )
        await UniMessage.image(raw=pic).finish(reply_to=True)
    else:
        await UniMessage.text(f"{NGM[state['mode']]}模式暂不支持预览").finish()