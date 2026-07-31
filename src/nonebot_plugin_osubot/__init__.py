from pathlib import Path

from nonebot import get_driver, require
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")
require("nonebot_plugin_session")
require("nonebot_plugin_orm")

# OSUBot 的绘图功能依赖 Playwright，并需要读取自身模板资源。用户显式选择
# 其他 Provider 时保持其配置；未配置时沿用插件此前的 Playwright 默认值。
driver = get_driver()
render_config = getattr(driver.config, "render", None)
if render_config is None or isinstance(render_config, dict):
    render_values = dict(render_config or {})
    render_values.setdefault("provider", "playwright")

    resources = dict(render_values.get("resources") or {})
    local_access = dict(resources.get("local_access") or {})
    allowed_paths = list(local_access.get("allowed_paths") or [])
    draw_path = str((Path(__file__).parent / "draw").resolve())
    if draw_path not in {str(path) for path in allowed_paths}:
        allowed_paths.append(draw_path)
    local_access["allowed_paths"] = allowed_paths
    resources["local_access"] = local_access
    render_values["resources"] = resources
    driver.config.render = render_values

require("nonebot_plugin_htmlrender")
require("nonebot_plugin_waiter")
require("nonebot_plugin_uninfo")
import asyncio

from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from .config import Config
from .matcher import *  # noqa
from .info import update_users_info
from .draw.browser import close_persistent_pages
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


@driver.on_startup
async def _warm_up_pp_calculator():
    # 后台预热，不阻塞启动；首次 pp 计算有近 2s 的初始化开销
    from .pp import warm_up_pp_calculator

    asyncio.create_task(warm_up_pp_calculator())


driver.on_shutdown(close_persistent_pages)
