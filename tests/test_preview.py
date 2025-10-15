"""测试预览和转换相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_generate_preview_matcher_exists(app: App):
    """测试 generate_preview matcher 存在"""
    from nonebot_plugin_osubot.matcher import generate_preview
    
    assert generate_preview is not None


@pytest.mark.asyncio
async def test_generate_preview_matcher_priority(app: App):
    """测试 generate_preview matcher 优先级"""
    from nonebot_plugin_osubot.matcher.preview import generate_preview
    
    assert generate_preview.priority == 11


@pytest.mark.asyncio
async def test_generate_preview_matcher_block(app: App):
    """测试 generate_preview matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.preview import generate_preview
    
    assert generate_preview.block == True


@pytest.mark.asyncio
async def test_convert_matcher_exists(app: App):
    """测试 convert matcher 存在"""
    from nonebot_plugin_osubot.matcher import convert
    
    assert convert is not None


@pytest.mark.asyncio
async def test_change_matcher_exists(app: App):
    """测试 change matcher 存在"""
    from nonebot_plugin_osubot.matcher import change
    
    assert change is not None


@pytest.mark.asyncio
async def test_generate_full_ln_matcher_exists(app: App):
    """测试 generate_full_ln matcher 存在"""
    from nonebot_plugin_osubot.matcher import generate_full_ln
    
    assert generate_full_ln is not None


@pytest.mark.asyncio
async def test_convert_matcher_priority(app: App):
    """测试 convert matcher 优先级"""
    from nonebot_plugin_osubot.matcher.map_convert import convert
    
    assert convert.priority == 11


@pytest.mark.asyncio
async def test_change_matcher_priority(app: App):
    """测试 change matcher 优先级"""
    from nonebot_plugin_osubot.matcher.map_convert import change
    
    assert change.priority == 11


@pytest.mark.asyncio
async def test_generate_full_ln_matcher_priority(app: App):
    """测试 generate_full_ln matcher 优先级"""
    from nonebot_plugin_osubot.matcher.map_convert import generate_full_ln
    
    assert generate_full_ln.priority == 11


@pytest.mark.asyncio
async def test_convert_matcher_block(app: App):
    """测试 convert matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.map_convert import convert
    
    assert convert.block == True


@pytest.mark.asyncio
async def test_change_matcher_block(app: App):
    """测试 change matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.map_convert import change
    
    assert change.block == True


@pytest.mark.asyncio
async def test_generate_full_ln_matcher_block(app: App):
    """测试 generate_full_ln matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.map_convert import generate_full_ln
    
    assert generate_full_ln.block == True


@pytest.mark.asyncio
async def test_generate_preview_has_handler(app: App):
    """测试 generate_preview matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.preview import generate_preview
    
    assert len(generate_preview.handlers) > 0, "generate_preview matcher 应该有处理器"


@pytest.mark.asyncio
async def test_convert_has_handler(app: App):
    """测试 convert matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.map_convert import convert
    
    assert len(convert.handlers) > 0, "convert matcher 应该有处理器"


@pytest.mark.asyncio
async def test_change_has_handler(app: App):
    """测试 change matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.map_convert import change
    
    assert len(change.handlers) > 0, "change matcher 应该有处理器"


@pytest.mark.asyncio
async def test_generate_full_ln_has_handler(app: App):
    """测试 generate_full_ln matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.map_convert import generate_full_ln
    
    assert len(generate_full_ln.handlers) > 0, "generate_full_ln matcher 应该有处理器"
