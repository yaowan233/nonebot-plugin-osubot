from pathlib import Path

from nonebot import on_command
from nonebot.adapters.red import MessageEvent as RedMessageEvent, MessageSegment as RedMessageSegment
from nonebot.adapters.onebot.v11 import MessageEvent as v11MessageEvent, MessageSegment as v11MessageSegment

osu_help = on_command('osuhelp', priority=11, block=True)
with open(Path(__file__).parent.parent / 'osufile' / 'help.png', 'rb') as f:
    img1 = f.read()
with open(Path(__file__).parent.parent / 'osufile' / 'detail.png', 'rb') as f:
    img2 = f.read()


@osu_help.handle()
async def _help(event: v11MessageEvent):
    arg = event.message.extract_plain_text().strip()
    if arg == 'detail':
        await osu_help.finish(v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(img2))
    await osu_help.finish(v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(img1))


@osu_help.handle()
async def _help(event: RedMessageEvent):
    arg = event.message.extract_plain_text().strip()
    if arg == 'detail':
        await osu_help.finish(RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + RedMessageSegment.image(img2))
    await osu_help.finish(RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + RedMessageSegment.image(img1))
