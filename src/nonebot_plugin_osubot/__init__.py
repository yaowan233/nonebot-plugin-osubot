from collections.abc import Mapping
from pathlib import Path

from nonebot import get_driver, get_loaded_plugins, get_plugin_config, require
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")
require("nonebot_plugin_session")
require("nonebot_plugin_orm")

# OSUBot 的绘图功能依赖 Playwright，并需要读取自身模板资源。用户显式选择
# 其他 Provider 时保持其配置；未配置时沿用插件此前的 Playwright 默认值。
driver = get_driver()
htmlrender_preloaded = any(plugin.name == "nonebot_plugin_htmlrender" for plugin in get_loaded_plugins())
render_config = getattr(driver.config, "render", None)
if render_config is None or isinstance(render_config, Mapping) or callable(getattr(render_config, "model_dump", None)):
    if render_config is None:
        render_values = {}
    elif isinstance(render_config, Mapping):
        render_values = dict(render_config)
    else:
        render_values = render_config.model_dump(mode="python")
    if render_values.get("provider") is None:
        render_values["provider"] = "playwright"

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
if htmlrender_preloaded:
    # HTMLRender 0.8 在首次导入时固定默认 Application 的 composition。
    # 如果其他插件先导入了它，仅修改 NoneBot 配置并不会更新旧 composition，
    # 需要在补齐 Playwright 配置后重新初始化默认 Application。
    from nonebot_plugin_htmlrender import initialize_plugin

    initialize_plugin()
require("nonebot_plugin_waiter")
require("nonebot_plugin_uninfo")
import asyncio

from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from .config import Config
from .matcher import *  # noqa
from .info import update_users_info
from .api import close_osu_api_network
from .draw.browser import close_persistent_pages
from .database.models import UserData
from .network.scheduler import RequestPriority, osu_api_priority

plugin_config = get_plugin_config(Config)

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


@scheduler.scheduled_job("cron", hour="0", coalesce=True, max_instances=1, misfire_grace_time=60)
async def update_info():
    async with get_session() as session:
        users = list(await session.scalars(select(UserData.osu_id).distinct()))
    if not users:
        return
    groups = [users[i : i + 50] for i in range(0, len(users), 50)]
    with osu_api_priority(RequestPriority.BACKGROUND):
        for group in groups:
            await update_users_info(group)
    logger.info(f"已更新{len(users)}位玩家数据")


@scheduler.scheduled_job(
    "cron",
    hour=plugin_config.osu_score_history_sync_hour,
    coalesce=True,
    max_instances=1,
    misfire_grace_time=3600,
)
async def update_score_history():
    if not plugin_config.osu_score_history_enabled:
        return

    from .score_collector import collect_active_score_history

    await collect_active_score_history(
        concurrency=plugin_config.osu_score_history_concurrency,
        recent_limit=plugin_config.osu_score_history_recent_limit,
    )


@driver.on_startup
async def _warm_up_pp_calculator():
    # 后台预热，不阻塞启动；首次 pp 计算和原生出图都有初始化开销
    from .draw.svg_render import warm_up_native_renderer
    from .pp import warm_up_pp_calculator

    asyncio.create_task(warm_up_pp_calculator())
    asyncio.create_task(warm_up_native_renderer())


driver.on_shutdown(close_persistent_pages)
driver.on_shutdown(close_osu_api_network)
