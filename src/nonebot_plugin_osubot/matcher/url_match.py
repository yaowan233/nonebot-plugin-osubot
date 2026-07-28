from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage

from .map_context import remember_map_and_set, remember_set
from ..api import osu_api
from ..draw import draw_bmap_info, draw_map_info

url_match = on_regex(r"https?://osu\.ppy\.sh/(?:(?:beatmapsets/(\d+)(?:#[^/\s]+/(\d+))?)|(?:(?:b|beatmaps)/(\d+)))")
url = "https://catboy.best/d/"
url_1 = "https://osu.direct/api/d/"
url_2 = "https://txy1.sayobot.cn/beatmaps/download/novideo/"


@url_match.handle()
async def _url(event: Event, bid: tuple = RegexGroup()):
    set_id, set_map_id, direct_map_id = bid
    beatmap_id = set_map_id or direct_map_id
    try:
        if beatmap_id:
            if not set_id:
                map_data = await osu_api("map", map_id=int(beatmap_id))
                set_id = str(map_data["beatmapset_id"])
            image = await draw_map_info(beatmap_id, [])
            remember_map_and_set(event, beatmap_id, set_id)
        else:
            image = await draw_bmap_info(set_id)
            remember_set(event, set_id)
    except Exception:
        return
    url_total = f"镜像站1：{url}{set_id}\n镜像站2：{url_1}{set_id}\n小夜镜像站：{url_2}{set_id}"
    await (UniMessage.image(raw=image) + "\n" + url_total).finish(reply_to=True)
