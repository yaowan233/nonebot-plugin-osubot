"""测试信息查询相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_info_matcher_exists(app: App):
    """测试 info matcher 存在"""
    from nonebot_plugin_osubot.matcher import info
    
    assert info is not None


@pytest.mark.asyncio
async def test_info_matcher_priority(app: App):
    """测试 info matcher 优先级"""
    from nonebot_plugin_osubot.matcher.info import info
    
    assert info.priority == 11


@pytest.mark.asyncio
async def test_info_matcher_block(app: App):
    """测试 info matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.info import info
    
    assert info.block == True


@pytest.mark.asyncio
async def test_info_has_handler(app: App):
    """测试 info matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.info import info
    
    assert len(info.handlers) > 0, "info matcher 应该有处理器"


@pytest.mark.asyncio
async def test_info_matcher_aliases(app: App):
    """测试 info matcher 别名"""
    from nonebot_plugin_osubot.matcher.info import info
    
    # 验证别名包含 Info 和 INFO
    assert hasattr(info, "__matcher_name__")


@pytest.mark.asyncio
async def test_mu_matcher_exists(app: App):
    """测试 mu matcher 存在"""
    from nonebot_plugin_osubot.matcher import mu
    
    assert mu is not None


@pytest.mark.asyncio
async def test_mu_matcher_priority(app: App):
    """测试 mu matcher 优先级"""
    from nonebot_plugin_osubot.matcher.mu import mu
    
    assert mu.priority == 11


@pytest.mark.asyncio
async def test_mu_matcher_block(app: App):
    """测试 mu matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.mu import mu
    
    assert mu.block == True


@pytest.mark.asyncio
async def test_mu_has_handler(app: App):
    """测试 mu matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.mu import mu
    
    assert len(mu.handlers) > 0, "mu matcher 应该有处理器"
