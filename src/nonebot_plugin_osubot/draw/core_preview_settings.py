"""One consistent configuration for the process-wide native renderer."""

import json

from nonebot import get_plugin_config

from ..config import Config

plugin_config = get_plugin_config(Config)


def native_render_config() -> str | None:
    # Upstream initializes configuration once per process. All beatmap, replay
    # and recovery calls must supply the same auth configuration from the start.
    if not plugin_config.osu_client or not plugin_config.osu_key:
        return None
    return json.dumps(
        {
            "download": {
                "auth": {
                    "OSU_CLIENT_ID": str(plugin_config.osu_client),
                    "OSU_CLIENT_SECRET": plugin_config.osu_key,
                }
            }
        }
    )
