"""测试其他杂项 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_osu_help_matcher_exists(app: App):
    """测试 osu_help matcher 存在"""
    from nonebot_plugin_osubot.matcher import osu_help
    
    assert osu_help is not None


@pytest.mark.asyncio
async def test_osu_help_matcher_priority(app: App):
    """测试 osu_help matcher 优先级"""
    from nonebot_plugin_osubot.matcher.osu_help import osu_help
    
    assert osu_help.priority == 11


@pytest.mark.asyncio
async def test_osu_help_matcher_block(app: App):
    """测试 osu_help matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.osu_help import osu_help
    
    assert osu_help.block == True


@pytest.mark.asyncio
async def test_url_match_matcher_exists(app: App):
    """测试 url_match matcher 存在"""
    from nonebot_plugin_osubot.matcher import url_match
    
    assert url_match is not None


@pytest.mark.asyncio
async def test_recommend_matcher_exists(app: App):
    """测试 recommend matcher 存在"""
    from nonebot_plugin_osubot.matcher import recommend
    
    assert recommend is not None


@pytest.mark.asyncio
async def test_recommend_matcher_priority(app: App):
    """测试 recommend matcher 优先级"""
    from nonebot_plugin_osubot.matcher.recommend import recommend
    
    assert recommend.priority == 11


@pytest.mark.asyncio
async def test_recommend_matcher_block(app: App):
    """测试 recommend matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.recommend import recommend
    
    assert recommend.block == True


@pytest.mark.asyncio
async def test_match_matcher_exists(app: App):
    """测试 match matcher 存在"""
    from nonebot_plugin_osubot.matcher import match
    
    assert match is not None


@pytest.mark.asyncio
async def test_match_matcher_priority(app: App):
    """测试 match matcher 优先级"""
    from nonebot_plugin_osubot.matcher.match import match
    
    assert match.priority == 11


@pytest.mark.asyncio
async def test_match_matcher_block(app: App):
    """测试 match matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.match import match
    
    assert match.block == True


@pytest.mark.asyncio
async def test_medal_matcher_exists(app: App):
    """测试 medal matcher 存在"""
    from nonebot_plugin_osubot.matcher import medal
    
    assert medal is not None


@pytest.mark.asyncio
async def test_medal_matcher_priority(app: App):
    """测试 medal matcher 优先级"""
    from nonebot_plugin_osubot.matcher.medal import medal
    
    assert medal.priority == 11


@pytest.mark.asyncio
async def test_medal_matcher_block(app: App):
    """测试 medal matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.medal import medal
    
    assert medal.block == True


@pytest.mark.asyncio
async def test_osudl_matcher_exists(app: App):
    """测试 osudl matcher 存在"""
    from nonebot_plugin_osubot.matcher import osudl
    
    assert osudl is not None


@pytest.mark.asyncio
async def test_osudl_matcher_priority(app: App):
    """测试 osudl matcher 优先级"""
    from nonebot_plugin_osubot.matcher.osudl import osudl
    
    assert osudl.priority == 11


@pytest.mark.asyncio
async def test_osudl_matcher_block(app: App):
    """测试 osudl matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.osudl import osudl
    
    assert osudl.block == True


@pytest.mark.asyncio
async def test_history_matcher_exists(app: App):
    """测试 history matcher 存在"""
    from nonebot_plugin_osubot.matcher import history
    
    assert history is not None


@pytest.mark.asyncio
async def test_history_matcher_priority(app: App):
    """测试 history matcher 优先级"""
    from nonebot_plugin_osubot.matcher.history import history
    
    assert history.priority == 11


@pytest.mark.asyncio
async def test_history_matcher_block(app: App):
    """测试 history matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.history import history
    
    assert history.block == True


@pytest.mark.asyncio
async def test_rating_matcher_exists(app: App):
    """测试 rating matcher 存在"""
    from nonebot_plugin_osubot.matcher import rating
    
    assert rating is not None


@pytest.mark.asyncio
async def test_rating_matcher_priority(app: App):
    """测试 rating matcher 优先级"""
    from nonebot_plugin_osubot.matcher.rating import rating
    
    assert rating.priority == 11


@pytest.mark.asyncio
async def test_rating_matcher_block(app: App):
    """测试 rating matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.rating import rating
    
    assert rating.block == True


@pytest.mark.asyncio
async def test_group_pp_rank_matcher_exists(app: App):
    """测试 group_pp_rank matcher 存在"""
    from nonebot_plugin_osubot.matcher import group_pp_rank
    
    assert group_pp_rank is not None


@pytest.mark.asyncio
async def test_group_pp_rank_matcher_priority(app: App):
    """测试 group_pp_rank matcher 优先级"""
    from nonebot_plugin_osubot.matcher.rank import group_pp_rank
    
    assert group_pp_rank.priority == 11


@pytest.mark.asyncio
async def test_group_pp_rank_matcher_block(app: App):
    """测试 group_pp_rank matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.rank import group_pp_rank
    
    assert group_pp_rank.block == True
