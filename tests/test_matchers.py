"""测试所有 matcher 的基本可用性"""
import pytest
from nonebug import App


@pytest.mark.asyncio
async def test_matchers_import(app: App):
    """测试所有 matcher 可以正常导入"""
    from nonebot_plugin_osubot.matcher import (
        bind,
        unbind,
        bp,
        tbp,
        getbg,
        guess_audio,
        guess_pic,
        word_matcher,
        pic_word_matcher,
        hint,
        pic_hint,
        history,
        info,
        bmap,
        osu_map,
        match,
        medal,
        mu,
        osu_help,
        osudl,
        pr,
        recent,
        generate_preview,
        group_pp_rank,
        rating,
        recommend,
        score,
        update_pic,
        update_info,
        clear_background,
        update_mode,
        url_match,
        bp_analyze,
        convert,
        change,
        generate_full_ln,
    )

    # 验证所有 matcher 都已成功导入
    assert bind is not None
    assert unbind is not None
    assert bp is not None
    assert tbp is not None
    assert getbg is not None
    assert guess_audio is not None
    assert guess_pic is not None
    assert word_matcher is not None
    assert pic_word_matcher is not None
    assert hint is not None
    assert pic_hint is not None
    assert history is not None
    assert info is not None
    assert bmap is not None
    assert osu_map is not None
    assert match is not None
    assert medal is not None
    assert mu is not None
    assert osu_help is not None
    assert osudl is not None
    assert pr is not None
    assert recent is not None
    assert generate_preview is not None
    assert group_pp_rank is not None
    assert rating is not None
    assert recommend is not None
    assert score is not None
    assert update_pic is not None
    assert update_info is not None
    assert clear_background is not None
    assert update_mode is not None
    assert url_match is not None
    assert bp_analyze is not None
    assert convert is not None
    assert change is not None
    assert generate_full_ln is not None


@pytest.mark.asyncio
async def test_bind_matcher_type(app: App):
    """测试 bind matcher 类型"""
    from nonebot_plugin_osubot.matcher import bind
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(bind), type(Matcher))


@pytest.mark.asyncio
async def test_bp_matcher_type(app: App):
    """测试 bp matcher 类型"""
    from nonebot_plugin_osubot.matcher import bp
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(bp), type(Matcher))


@pytest.mark.asyncio
async def test_info_matcher_type(app: App):
    """测试 info matcher 类型"""
    from nonebot_plugin_osubot.matcher import info
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(info), type(Matcher))


@pytest.mark.asyncio
async def test_mu_matcher_type(app: App):
    """测试 mu matcher 类型"""
    from nonebot_plugin_osubot.matcher import mu
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(mu), type(Matcher))


@pytest.mark.asyncio
async def test_getbg_matcher_type(app: App):
    """测试 getbg matcher 类型"""
    from nonebot_plugin_osubot.matcher import getbg
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(getbg), type(Matcher))


@pytest.mark.asyncio
async def test_osu_help_matcher_type(app: App):
    """测试 osu_help matcher 类型"""
    from nonebot_plugin_osubot.matcher import osu_help
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(osu_help), type(Matcher))


@pytest.mark.asyncio
async def test_recommend_matcher_type(app: App):
    """测试 recommend matcher 类型"""
    from nonebot_plugin_osubot.matcher import recommend
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(recommend), type(Matcher))


@pytest.mark.asyncio
async def test_url_match_matcher_type(app: App):
    """测试 url_match matcher 类型"""
    from nonebot_plugin_osubot.matcher import url_match
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(url_match), type(Matcher))


@pytest.mark.asyncio
async def test_update_mode_matcher_type(app: App):
    """测试 update_mode matcher 类型"""
    from nonebot_plugin_osubot.matcher import update_mode
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(update_mode), type(Matcher))


@pytest.mark.asyncio
async def test_match_matcher_type(app: App):
    """测试 match matcher 类型"""
    from nonebot_plugin_osubot.matcher import match
    from nonebot.internal.matcher import Matcher

    assert issubclass(type(match), type(Matcher))
