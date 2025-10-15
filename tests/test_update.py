"""测试更新相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_update_pic_matcher_exists(app: App):
    """测试 update_pic matcher 存在"""
    from nonebot_plugin_osubot.matcher import update_pic
    
    assert update_pic is not None


@pytest.mark.asyncio
async def test_update_info_matcher_exists(app: App):
    """测试 update_info matcher 存在"""
    from nonebot_plugin_osubot.matcher import update_info
    
    assert update_info is not None


@pytest.mark.asyncio
async def test_clear_background_matcher_exists(app: App):
    """测试 clear_background matcher 存在"""
    from nonebot_plugin_osubot.matcher import clear_background
    
    assert clear_background is not None


@pytest.mark.asyncio
async def test_update_mode_matcher_exists(app: App):
    """测试 update_mode matcher 存在"""
    from nonebot_plugin_osubot.matcher import update_mode
    
    assert update_mode is not None


@pytest.mark.asyncio
async def test_update_pic_matcher_priority(app: App):
    """测试 update_pic matcher 优先级"""
    from nonebot_plugin_osubot.matcher.update import update_pic
    
    assert update_pic.priority == 11


@pytest.mark.asyncio
async def test_update_info_matcher_priority(app: App):
    """测试 update_info matcher 优先级"""
    from nonebot_plugin_osubot.matcher.update import update_info
    
    assert update_info.priority == 11


@pytest.mark.asyncio
async def test_clear_background_matcher_priority(app: App):
    """测试 clear_background matcher 优先级"""
    from nonebot_plugin_osubot.matcher.update import clear_background
    
    assert clear_background.priority == 11


@pytest.mark.asyncio
async def test_update_mode_matcher_priority(app: App):
    """测试 update_mode matcher 优先级"""
    from nonebot_plugin_osubot.matcher.update_mode import update_mode
    
    assert update_mode.priority == 11


@pytest.mark.asyncio
async def test_update_pic_matcher_block(app: App):
    """测试 update_pic matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.update import update_pic
    
    assert update_pic.block == True


@pytest.mark.asyncio
async def test_update_info_matcher_block(app: App):
    """测试 update_info matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.update import update_info
    
    assert update_info.block == True


@pytest.mark.asyncio
async def test_clear_background_matcher_block(app: App):
    """测试 clear_background matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.update import clear_background
    
    assert clear_background.block == True


@pytest.mark.asyncio
async def test_update_mode_matcher_block(app: App):
    """测试 update_mode matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.update_mode import update_mode
    
    assert update_mode.block == True
