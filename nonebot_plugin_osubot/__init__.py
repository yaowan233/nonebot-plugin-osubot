from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.log import logger
from nonebot import require

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")
require("nonebot_plugin_session")
require("nonebot_plugin_tortoise_orm")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_waiter")
from .database.models import UserData
from .info import update_users_info
from .config import Config
from .matcher import *  # noqa
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_tortoise_orm import add_model


add_model("nonebot_plugin_osubot.database.models")
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
    result = await UserData.all()
    if not result:
        return
    users = [i.osu_id for i in result]
    groups = [users[i : i + 50] for i in range(0, len(users), 50)]
    for group in groups:
        await update_users_info(group)
    logger.info(f"已更新{len(result)}位玩家数据")
