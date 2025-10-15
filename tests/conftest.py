import pytest
from nonebug import App
from pathlib import Path


@pytest.fixture
async def app(tmp_path: Path):
    """创建测试用的 NoneBot App"""
    # 设置临时配置
    import nonebot
    
    # 创建 App 实例
    app = App()
    
    return app
