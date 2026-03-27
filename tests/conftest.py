import os

import pytest
import nonebot
from pytest_asyncio import is_async_test
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter

os.environ["ENVIRONMENT"] = "test"


def pytest_collection_modifyitems(items: list[pytest.Item]):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None):
    driver = nonebot.get_driver()
    driver.register_adapter(OnebotV11Adapter)
    nonebot.load_plugin("nonebot_plugin_osubot")

    from nonebot_plugin_orm import init_orm

    await init_orm()

    import nonebot_plugin_orm

    for bind, engine in nonebot_plugin_orm._engines.items():
        metadata = nonebot_plugin_orm._metadatas.get(bind)
        if metadata is not None:
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)

    # matcher/__init__.py 做了 `from .bind import bind` 等 re-export，
    # 导致 nonebot_plugin_osubot.matcher.bind 这个 attribute 指向 Matcher 对象
    # 而非子模块。patch("...matcher.bind.get_session") 在 Python 3.10 里走
    # getattr 路径，会拿到 Matcher 对象而报 AttributeError。
    # 插件加载完毕后把所有直接子模块的 attribute 还原为模块本身。
    import sys
    import nonebot_plugin_osubot.matcher as _matcher_pkg

    for _mod_path, _mod in list(sys.modules.items()):
        if (
            _mod is not None
            and _mod_path.startswith("nonebot_plugin_osubot.matcher.")
            and _mod_path.count(".") == 3
        ):
            setattr(_matcher_pkg, _mod_path.rsplit(".", 1)[1], _mod)
