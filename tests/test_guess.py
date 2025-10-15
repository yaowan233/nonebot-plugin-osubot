"""测试游戏相关的 matcher"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_guess_audio_matcher_exists(app: App):
    """测试 guess_audio matcher 存在"""
    from nonebot_plugin_osubot.matcher import guess_audio
    
    assert guess_audio is not None


@pytest.mark.asyncio
async def test_guess_pic_matcher_exists(app: App):
    """测试 guess_pic matcher 存在"""
    from nonebot_plugin_osubot.matcher import guess_pic
    
    assert guess_pic is not None


@pytest.mark.asyncio
async def test_word_matcher_exists(app: App):
    """测试 word_matcher 存在"""
    from nonebot_plugin_osubot.matcher import word_matcher
    
    assert word_matcher is not None


@pytest.mark.asyncio
async def test_pic_word_matcher_exists(app: App):
    """测试 pic_word_matcher 存在"""
    from nonebot_plugin_osubot.matcher import pic_word_matcher
    
    assert pic_word_matcher is not None


@pytest.mark.asyncio
async def test_hint_matcher_exists(app: App):
    """测试 hint matcher 存在"""
    from nonebot_plugin_osubot.matcher import hint
    
    assert hint is not None


@pytest.mark.asyncio
async def test_pic_hint_matcher_exists(app: App):
    """测试 pic_hint matcher 存在"""
    from nonebot_plugin_osubot.matcher import pic_hint
    
    assert pic_hint is not None


@pytest.mark.asyncio
async def test_guess_audio_matcher_priority(app: App):
    """测试 guess_audio matcher 优先级"""
    from nonebot_plugin_osubot.matcher.guess import guess_audio
    
    assert guess_audio.priority == 11


@pytest.mark.asyncio
async def test_guess_pic_matcher_priority(app: App):
    """测试 guess_pic matcher 优先级"""
    from nonebot_plugin_osubot.matcher.guess import guess_pic
    
    assert guess_pic.priority == 11


@pytest.mark.asyncio
async def test_hint_matcher_priority(app: App):
    """测试 hint matcher 优先级"""
    from nonebot_plugin_osubot.matcher.guess import hint
    
    assert hint.priority == 11


@pytest.mark.asyncio
async def test_pic_hint_matcher_priority(app: App):
    """测试 pic_hint matcher 优先级"""
    from nonebot_plugin_osubot.matcher.guess import pic_hint
    
    assert pic_hint.priority == 11


@pytest.mark.asyncio
async def test_guess_audio_matcher_block(app: App):
    """测试 guess_audio matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.guess import guess_audio
    
    assert guess_audio.block == True


@pytest.mark.asyncio
async def test_guess_pic_matcher_block(app: App):
    """测试 guess_pic matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.guess import guess_pic
    
    assert guess_pic.block == True


@pytest.mark.asyncio
async def test_hint_matcher_block(app: App):
    """测试 hint matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.guess import hint
    
    assert hint.block == True


@pytest.mark.asyncio
async def test_pic_hint_matcher_block(app: App):
    """测试 pic_hint matcher 是否阻断"""
    from nonebot_plugin_osubot.matcher.guess import pic_hint
    
    assert pic_hint.block == True


@pytest.mark.asyncio
async def test_guess_audio_has_handler(app: App):
    """测试 guess_audio matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.guess import guess_audio
    
    assert len(guess_audio.handlers) > 0, "guess_audio matcher 应该有处理器"


@pytest.mark.asyncio
async def test_guess_pic_has_handler(app: App):
    """测试 guess_pic matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.guess import guess_pic
    
    assert len(guess_pic.handlers) > 0, "guess_pic matcher 应该有处理器"


@pytest.mark.asyncio
async def test_hint_has_handler(app: App):
    """测试 hint matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.guess import hint
    
    assert len(hint.handlers) > 0, "hint matcher 应该有处理器"


@pytest.mark.asyncio
async def test_pic_hint_has_handler(app: App):
    """测试 pic_hint matcher 有处理器"""
    from nonebot_plugin_osubot.matcher.guess import pic_hint
    
    assert len(pic_hint.handlers) > 0, "pic_hint matcher 应该有处理器"
