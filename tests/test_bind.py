"""测试绑定相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_bind_matcher_exists(app: App):
    """测试 bind matcher 存在"""
    from nonebot_plugin_osubot.matcher import bind
    
    assert bind is not None


@pytest.mark.asyncio
async def test_unbind_matcher_exists(app: App):
    """测试 unbind matcher 存在"""
    from nonebot_plugin_osubot.matcher import unbind
    
    assert unbind is not None


@pytest.mark.asyncio
async def test_bind_matcher_priority(app: App):
    """测试 bind matcher 优先级"""
    from nonebot_plugin_osubot.matcher.bind import bind
    
    assert bind.priority == 11


@pytest.mark.asyncio
async def test_unbind_matcher_priority(app: App):
    """测试 unbind matcher 优先级"""
    from nonebot_plugin_osubot.matcher.bind import unbind
    
    assert unbind.priority == 11


@pytest.mark.asyncio
async def test_bind_matcher_block(app: App):
    """测试 bind matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.bind import bind
    
    assert bind.block == True


@pytest.mark.asyncio
async def test_unbind_matcher_block(app: App):
    """测试 unbind matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.bind import unbind
    
    assert unbind.block == True
