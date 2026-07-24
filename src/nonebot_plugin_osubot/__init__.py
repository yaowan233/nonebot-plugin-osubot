from nonebot import require
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")
require("nonebot_plugin_session")
require("nonebot_plugin_orm")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_waiter")
require("nonebot_plugin_uninfo")
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_htmlrender.config import plugin_config as htmlrender_config
from nonebot_plugin_htmlrender.consts import RenderBackend
from nonebot_plugin_orm import get_session
from sqlalchemy import select

if htmlrender_config.render_backend is None:
    htmlrender_config.render_backend = RenderBackend.PLAYWRIGHT

from .config import Config
from .matcher import *  # noqa
from .info import update_users_info
from .database.models import UserData

try:
    require("nonebot_plugin_ai_groupmate")
except ModuleNotFoundError as e:
    if e.name != "nonebot_plugin_ai_groupmate":
        raise
    logger.debug(f"ai-groupmate agent tools not enabled: {e}")
except RuntimeError as e:
    if "nonebot_plugin_ai_groupmate" not in str(e):
        raise
    logger.debug(f"ai-groupmate agent tools not enabled: {e}")
else:
    from . import agent_tools as agent_tools  # noqa: F401

usage = "发送/osuhelp 查看帮助"
__plugin_meta__ = PluginMetadata(
    name="OSUBot",
    description="OSU查分插件",
    usage=usage,
    type="application",
    homepage="https://github.com/yaowan233/nonebot-plugin-osubot",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_session", "nonebot_plugin_alconna"),
    extra={
        "unique_name": "osubot",
        "author": "yaowan233 <572473053@qq.com>",
    },
)


@scheduler.scheduled_job("cron", hour="0", misfire_grace_time=60)
async def update_info():
    async with get_session() as session:
        result = (await session.scalars(select(UserData))).all()
    if not result:
        return
    users = [i.osu_id for i in result]
    groups = [users[i : i + 50] for i in range(0, len(users), 50)]
    for group in groups:
        await update_users_info(group)
    logger.info(f"已更新{len(result)}位玩家数据")
