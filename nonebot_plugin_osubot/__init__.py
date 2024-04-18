import shutil
from pathlib import Path
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.log import logger
from nonebot import require

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")
require("nonebot_plugin_session")
require("nonebot_plugin_tortoise_orm")
from .database.models import UserData
from .info import update_user_info
from .config import Config
from .matcher import *
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
    supported_adapters=inherit_supported_adapters("nonebot_plugin_session"),
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
    for user in result:
        await update_user_info(user.osu_id)
    logger.info(f"已更新{len(result)}位玩家数据")


@scheduler.scheduled_job("cron", hour="4", day_of_week="0", misfire_grace_time=60)
async def delete_cached_map():
    map_path = Path("data/osu/map")
    shutil.rmtree(map_path)
    map_path.mkdir(parents=True, exist_ok=True)
    user_path = Path("data/osu/user")
    for file_path in user_path.glob("**/*"):
        if file_path.is_file() and file_path.name in ("icon.png", "icon.gif"):
            file_path.unlink()
