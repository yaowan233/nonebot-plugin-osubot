import asyncio
import base64

from nonebot import on_command
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.internal.adapter import Bot, Message, Event
from nonebot_plugin_alconna import UniMessage

try:
    from nonebot.adapters.onebot.v11.exception import NetworkError
    from nonebot.adapters.onebot.v11 import Message as OB11Message  # noqa: F401
    from nonebot.adapters.onebot.v11 import MessageSegment  # noqa: F401

    _OB11_OK = True
except ImportError:
    _OB11_OK = False

    class NetworkError(Exception):
        pass


from ..draw.match_history import draw_match_history

match = on_command("match", aliases={"mp"}, priority=11, block=True)

SEND_RETRIES = 2
SEND_RETRY_INTERVAL = 2
USE_FORWARD = True  # 多图时用合并转发


async def _send_with_retry(coro_factory):
    """对一个『返回 awaitable 的工厂』做重试，仅捕获 NetworkError。"""
    for attempt in range(SEND_RETRIES + 1):
        try:
            return await coro_factory()
        except NetworkError:
            if attempt < SEND_RETRIES:
                await asyncio.sleep(SEND_RETRY_INTERVAL)
                continue
            raise


def _build_nodes(self_id: object, images: list[bytes]) -> list[dict]:
    """构造 OneBot v11 合并转发的标准 node 列表（原始 dict 形式，兼容性最好）。"""
    nodes = []
    for i, img in enumerate(images, start=1):
        b64 = base64.b64encode(img).decode()
        nodes.append(
            {
                "type": "node",
                "data": {
                    "user_id": str(self_id),
                    "nickname": f"osu! 多人房战报 ({i}/{len(images)})",
                    "content": [
                        {
                            "type": "image",
                            "data": {"file": f"base64://{b64}"},
                        }
                    ],
                },
            }
        )
    return nodes


async def _send_forward(bot, event, images: list[bytes]) -> bool:
    """尝试合并转发发送，成功返回 True，环境不支持返回 False。"""
    if not _OB11_OK:
        return False

    group_id = getattr(event, "group_id", None)
    user_id = getattr(event, "user_id", None)
    try:
        nodes = _build_nodes(bot.self_id, images)
    except Exception:
        return False

    try:
        if group_id is not None:
            await _send_with_retry(lambda: bot.call_api("send_group_forward_msg", group_id=group_id, messages=nodes))
        elif user_id is not None:
            await _send_with_retry(lambda: bot.call_api("send_private_forward_msg", user_id=user_id, messages=nodes))
        else:
            return False
        return True
    except Exception:
        return False


async def _send_one_by_one(images: list[bytes]):
    """退化方案：逐张发送。"""
    for index, img in enumerate(images):
        await _send_with_retry(lambda raw=img, first=(index == 0): UniMessage.image(raw=raw).send(reply_to=first))
        if index < len(images) - 1:
            await asyncio.sleep(0.5)


@match.handle()
async def _help(bot: Bot, arg: Message = CommandArg(), event: Event = None):
    arg = arg.extract_plain_text().strip()
    if not arg or not arg.isdigit():
        await match.finish("请输入比赛/多人房 ID，例如：/mp 3985712")
    try:
        pages = await draw_match_history(arg)
    except Exception as e:
        logger.opt(exception=e).error(f"绘制 match 历史失败: match_id={arg}")
        await match.finish(f"查询失败，请稍后再试或联系管理员\n错误信息: {e}")

    # 单图：直接回复发送
    if len(pages) == 1:
        await _send_with_retry(lambda: UniMessage.image(raw=pages[0]).finish(reply_to=True))
        return

    # 多图：优先合并转发，失败则逐张发送
    if USE_FORWARD:
        if await _send_forward(bot, event, pages):
            return

    await _send_one_by_one(pages)
