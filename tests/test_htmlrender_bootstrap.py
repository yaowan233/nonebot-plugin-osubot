import subprocess
import sys


def test_osubot_recomposes_preloaded_htmlrender_with_playwright():
    code = """
import nonebot

nonebot.init(render={"provider": None})
nonebot.load_plugin("nonebot_plugin_htmlrender")

from nonebot_plugin_htmlrender import get_default_application

old_application = get_default_application()
nonebot.load_plugin("nonebot_plugin_osubot")
new_application = get_default_application()

assert new_application is not old_application
assert new_application.extensions.playwright is not None
assert nonebot.get_driver().config.render["provider"] == "playwright"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
