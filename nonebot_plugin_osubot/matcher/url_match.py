from nonebot import on_regex
from nonebot_plugin_alconna import UniMessage
from ..draw import draw_map_info
from nonebot.typing import T_State
from nonebot.params import RegexGroup

url_match = on_regex("https://osu.ppy.sh/beatmapsets/([0-9]+)#([^/]+/[0-9]+)")
url_1 = "https://osu.direct/api/d/"
url_2 = "https://txy1.sayobot.cn/beatmaps/download/novideo/"


@url_match.handle()
async def _url(state: T_State, bid: tuple = RegexGroup()):
    beatmap_id = bid[1].split("/")[1]
    url_total = f"kitsu镜像站：{url_1}{bid[0]}\n小夜镜像站：{url_2}{bid[0]}"
    state["para"] = beatmap_id
    m = await draw_map_info(beatmap_id, [])
    await (UniMessage.image(raw=m) + "\n" + url_total).finish(reply_to=True)
