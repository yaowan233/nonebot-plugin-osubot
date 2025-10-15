import pytest
from nonebug import App


@pytest.fixture
async def app():
    """创建测试用的 NoneBot App"""
    return App()
