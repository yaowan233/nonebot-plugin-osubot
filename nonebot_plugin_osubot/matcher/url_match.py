from typing import Union

from nonebot import on_regex
from nonebot.adapters.red import (
    MessageEvent as RedMessageEvent,
    MessageSegment as RedMessageSegment,
)
from nonebot.adapters.onebot.v11 import (
    MessageEvent as v11MessageEvent,
    MessageSegment as v11MessageSegment,
)
from nonebot.params import RegexGroup
from nonebot_plugin_guild_patch import GuildMessageEvent

url_match = on_regex("https://osu.ppy.sh/beatmapsets/(.*)#")
url_1 = "https://osu.direct/api/d/"
url_2 = "https://txy1.sayobot.cn/beatmaps/download/novideo/"


@url_match.handle()
async def _url(
    event: Union[v11MessageEvent, GuildMessageEvent], bid: tuple = RegexGroup()
):
    url_total = f"kitsu镜像站：{url_1}{bid[0]}\n小夜镜像站：{url_2}{bid[0]}"
    await url_match.finish(v11MessageSegment.reply(event.message_id) + url_total)


@url_match.handle()
async def _url(event: RedMessageEvent, bid: tuple = RegexGroup()):
    url_total = f"kitsu镜像站：{url_1}{bid[0]}\n小夜镜像站：{url_2}{bid[0]}"
    await url_match.finish(
        RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + url_total
    )
