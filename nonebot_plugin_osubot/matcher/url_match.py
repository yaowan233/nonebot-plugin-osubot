from nonebot import on_regex
from .map import osu_map
from ..draw import draw_map_info
from nonebot.adapters.red import (
    MessageEvent as RedMessageEvent,
    MessageSegment as RedMessageSegment,
)
from nonebot.adapters.onebot.v11 import (
    MessageEvent as v11MessageEvent,
    MessageSegment as v11MessageSegment,
)
from nonebot.typing import T_State
from nonebot.params import RegexGroup

url_match = on_regex("https://osu.ppy.sh/beatmapsets/([0-9]+)#([^/]+/[0-9]+)")
url_1 = "https://osu.direct/api/d/"
url_2 = "https://txy1.sayobot.cn/beatmaps/download/novideo/"


@url_match.handle()
@osu_map.handle()
async def _url(
    state: T_State, event: v11MessageEvent, bid: tuple = RegexGroup()
):
    beatmap_id = bid[1].split('/')[1]
    url_total = f"kitsu镜像站：{url_1}{bid[0]}\n小夜镜像站：{url_2}{bid[0]}"
    state['para'] = beatmap_id
    state['mods'] = ''
    m = await draw_map_info(beatmap_id, state['mods'])
    await url_match.finish(v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(m) + '\n' + url_total)


@url_match.handle()
@osu_map.handle()
async def _url(state: T_State, event: RedMessageEvent, bid: tuple = RegexGroup()):
    beatmap_id = bid[1].split('/')[1]
    url_total = f"kitsu镜像站：{url_1}{bid[0]}\n小夜镜像站：{url_2}{bid[0]}"
    state['para'] = beatmap_id
    state['mods'] = ''
    m = await draw_map_info(beatmap_id, state['mods'])
    await url_match.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + RedMessageSegment.image(m) + '\n' + url_total
    )
