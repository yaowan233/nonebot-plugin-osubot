import math

from nonebot import on_command
from nonebot.typing import T_State
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from ..utils import NGM, normalize_map_mode
from ..api import osu_api
from .utils import split_msg
from .map_context import get_last_map_id, remember_map_and_set
from ..file import download_osu
from ..exceptions import NetworkError
from ..mania import generate_preview_pic
from ..draw.osu_preview import draw_osu_preview, draw_full_osu_preview
from ..draw.catch_preview import draw_cath_preview
from ..draw.taiko_preview import parse_map, map_to_image

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
    if is_video_command or is_gif_preview(state):
        is_full = command == "完整预览" or is_video_command
        if is_full:

            async def send_estimate(seconds: float) -> None:
                if seconds < 15:
                    return
                estimate = format_estimated_time(seconds)
                await UniMessage.text(f"正在生成完整预览，预计还需约{estimate}，请稍候…").send(reply_to=True)

            video = await draw_full_osu_preview(
                int(osu_id),
                data["beatmapset_id"],
                progress_callback=send_estimate,
            )
            msg = UniMessage.video(raw=video.read_bytes(), name=video.name)
        else:
            pic = await draw_osu_preview(int(osu_id), data["beatmapset_id"], False)
            msg = UniMessage.image(raw=pic)
        if state["mode"] == "0":
            msg += UniMessage.text(
                f"点击预览：\nhttps://beatmap.try-z.net/?b={osu_id}\nhttps://beatmap.try-z.net/dev/?b={osu_id}"
            )
        await msg.finish(reply_to=not is_full)

    if state["mode"] == "3":
        osu = await download_osu(data["beatmapset_id"], int(osu_id))
        if state["_prefix"]["command"][0] == "完整预览":
            pic = await generate_preview_pic(osu, True)
        else:
            pic = await generate_preview_pic(osu)
        await UniMessage.image(raw=pic).finish(reply_to=True)
    elif state["mode"] == "2":
        pic = await draw_cath_preview(int(osu_id), data["beatmapset_id"], state["mods"])
        await UniMessage.image(raw=pic).finish(reply_to=True)
    elif state["mode"] == "1":
        osu = await download_osu(data["beatmapset_id"], int(osu_id))
        beatmap = parse_map(osu)
        pic = map_to_image(beatmap)
        await UniMessage.image(raw=pic).finish(reply_to=True)
    elif state["mode"] == "0":
        pic = await draw_osu_preview(int(osu_id), data["beatmapset_id"])
        msg = UniMessage.image(raw=pic) + UniMessage.text(
            f"点击预览：\nhttps://beatmap.try-z.net/?b={osu_id}\nhttps://beatmap.try-z.net/dev/?b={osu_id}"
        )
        await msg.finish(reply_to=True)
    else:
        await UniMessage.text(f"{NGM[state['mode']]}模式暂不支持预览").finish()
