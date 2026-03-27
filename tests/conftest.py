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
