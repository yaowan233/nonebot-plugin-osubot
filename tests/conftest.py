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
    # 而非子模块。patch("...xxx.get_session") 在 Python 3.10 里走
    # getattr 路径，会拿到 Matcher 对象而报 AttributeError。
    # 同样的，nonebot_plugin_osubot.__init__ 的 `from .matcher import *`
    # 也会把 info 等 Matcher 对象带入顶层包，遮挡 info/ 等子包。
    # 插件加载完毕后把所有子模块的 attribute 还原。
    import sys

    _prefix = "nonebot_plugin_osubot."
    for _mod_path, _mod in list(sys.modules.items()):
        if _mod is None:
            continue
        if not _mod_path.startswith(_prefix):
            continue
        if _mod_path == _prefix.rstrip("."):
            continue
        _parent_path, _name = _mod_path.rsplit(".", 1)
        if not _parent_path.startswith(_prefix) and _parent_path != _prefix.rstrip("."):
            continue
        _parent = sys.modules.get(_parent_path)
        if _parent is not None:
            setattr(_parent, _name, _mod)
