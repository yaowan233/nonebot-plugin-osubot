"""测试成绩相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_score_matcher_exists(app: App):
    """测试 score matcher 存在"""
    from nonebot_plugin_osubot.matcher import score
    
    assert score is not None


@pytest.mark.asyncio
async def test_score_matcher_priority(app: App):
    """测试 score matcher 优先级"""
    from nonebot_plugin_osubot.matcher.score import score
    
    assert score.priority == 11


@pytest.mark.asyncio
async def test_score_matcher_block(app: App):
    """测试 score matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.score import score
    
    assert score.block == True


@pytest.mark.asyncio
async def test_score_has_handler(app: App):
    """测试 score matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.score import score
    
    assert len(score.handlers) > 0, "score matcher 应该有处理器"


@pytest.mark.asyncio
async def test_pr_matcher_exists(app: App):
    """测试 pr matcher 存在"""
    from nonebot_plugin_osubot.matcher import pr
    
    assert pr is not None


@pytest.mark.asyncio
async def test_recent_matcher_exists(app: App):
    """测试 recent matcher 存在"""
    from nonebot_plugin_osubot.matcher import recent
    
    assert recent is not None


@pytest.mark.asyncio
async def test_pr_matcher_priority(app: App):
    """测试 pr matcher 优先级"""
    from nonebot_plugin_osubot.matcher.pr import pr
    
    assert pr.priority == 11


@pytest.mark.asyncio
async def test_recent_matcher_priority(app: App):
    """测试 recent matcher 优先级"""
    from nonebot_plugin_osubot.matcher.pr import recent
    
    assert recent.priority == 11


@pytest.mark.asyncio
async def test_pr_matcher_block(app: App):
    """测试 pr matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.pr import pr
    
    assert pr.block == True


@pytest.mark.asyncio
async def test_recent_matcher_block(app: App):
    """测试 recent matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.pr import recent
    
    assert recent.block == True


@pytest.mark.asyncio
async def test_pr_has_handler(app: App):
    """测试 pr matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.pr import pr
    
    assert len(pr.handlers) > 0, "pr matcher 应该有处理器"


@pytest.mark.asyncio
async def test_recent_has_handler(app: App):
    """测试 recent matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.pr import recent
    
    assert len(recent.handlers) > 0, "recent matcher 应该有处理器"
