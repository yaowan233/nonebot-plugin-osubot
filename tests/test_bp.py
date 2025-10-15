"""测试 BP 相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_bp_matcher_exists(app: App):
    """测试 bp matcher 存在"""
    from nonebot_plugin_osubot.matcher import bp
    
    assert bp is not None


@pytest.mark.asyncio
async def test_tbp_matcher_exists(app: App):
    """测试 tbp matcher 存在"""
    from nonebot_plugin_osubot.matcher import tbp
    
    assert tbp is not None


@pytest.mark.asyncio
async def test_bp_matcher_priority(app: App):
    """测试 bp matcher 优先级"""
    from nonebot_plugin_osubot.matcher.bp import bp
    
    assert bp.priority == 11


@pytest.mark.asyncio
async def test_tbp_matcher_priority(app: App):
    """测试 tbp matcher 优先级"""
    from nonebot_plugin_osubot.matcher.bp import tbp
    
    assert tbp.priority == 11


@pytest.mark.asyncio
async def test_bp_matcher_block(app: App):
    """测试 bp matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.bp import bp
    
    assert bp.block == True


@pytest.mark.asyncio
async def test_tbp_matcher_block(app: App):
    """测试 tbp matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.bp import tbp
    
    assert tbp.block == True


@pytest.mark.asyncio
async def test_bp_has_handler(app: App):
    """测试 bp matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.bp import bp
    
    assert len(bp.handlers) > 0, "bp matcher 应该有处理器"


@pytest.mark.asyncio
async def test_tbp_has_handler(app: App):
    """测试 tbp matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.bp import tbp
    
    assert len(tbp.handlers) > 0, "tbp matcher 应该有处理器"


@pytest.mark.asyncio
async def test_bp_analyze_matcher_exists(app: App):
    """测试 bp_analyze matcher 存在"""
    from nonebot_plugin_osubot.matcher import bp_analyze
    
    assert bp_analyze is not None


@pytest.mark.asyncio
async def test_bp_analyze_matcher_priority(app: App):
    """测试 bp_analyze matcher 优先级"""
    from nonebot_plugin_osubot.matcher.bp_analyze import bp_analyze
    
    assert bp_analyze.priority == 11


@pytest.mark.asyncio
async def test_bp_analyze_has_handler(app: App):
    """测试 bp_analyze matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.bp_analyze import bp_analyze
    
    assert len(bp_analyze.handlers) > 0, "bp_analyze matcher 应该有处理器"
