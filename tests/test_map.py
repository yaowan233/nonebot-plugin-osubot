"""测试地图相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_bmap_matcher_exists(app: App):
    """测试 bmap matcher 存在"""
    from nonebot_plugin_osubot.matcher import bmap
    
    assert bmap is not None


@pytest.mark.asyncio
async def test_osu_map_matcher_exists(app: App):
    """测试 osu_map matcher 存在"""
    from nonebot_plugin_osubot.matcher import osu_map
    
    assert osu_map is not None


@pytest.mark.asyncio
async def test_bmap_matcher_priority(app: App):
    """测试 bmap matcher 优先级"""
    from nonebot_plugin_osubot.matcher.map import bmap
    
    assert bmap.priority == 11


@pytest.mark.asyncio
async def test_osu_map_matcher_priority(app: App):
    """测试 osu_map matcher 优先级"""
    from nonebot_plugin_osubot.matcher.map import osu_map
    
    assert osu_map.priority == 11


@pytest.mark.asyncio
async def test_bmap_matcher_block(app: App):
    """测试 bmap matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.map import bmap
    
    assert bmap.block == True


@pytest.mark.asyncio
async def test_osu_map_matcher_block(app: App):
    """测试 osu_map matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.map import osu_map
    
    assert osu_map.block == True


@pytest.mark.asyncio
async def test_getbg_matcher_exists(app: App):
    """测试 getbg matcher 存在"""
    from nonebot_plugin_osubot.matcher import getbg
    
    assert getbg is not None


@pytest.mark.asyncio
async def test_getbg_matcher_priority(app: App):
    """测试 getbg matcher 优先级"""
    from nonebot_plugin_osubot.matcher.getbg import getbg
    
    assert getbg.priority == 11


@pytest.mark.asyncio
async def test_getbg_matcher_block(app: App):
    """测试 getbg matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.getbg import getbg
    
    assert getbg.block == True
