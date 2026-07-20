"""Tests for the short recent/best score list commands."""

import base64
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter, Bot, Message, MessageSegment
from nonebug import App

from fake import fake_group_message_event_v11
from utils import make_mock_session, make_mock_user, patch_session

PR_MODULE = "nonebot_plugin_osubot.matcher.pr"
UTILS_MODULE = "nonebot_plugin_osubot.matcher.utils"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "matcher_name", "include_fails", "project"),
    [("/rl", "recent_list", True, "relist"), ("/pl", "pass_list", False, "prlist")],
)
async def test_score_list_defaults_to_top_30(
    app: App, command: str, matcher_name: str, include_fails: bool, project: str
):
    import nonebot

    pr_module = importlib.import_module(PR_MODULE)
    matcher = getattr(pr_module, matcher_name)
    session = make_mock_session()
    session.scalar.return_value = make_mock_user()
    score = SimpleNamespace()
    event = fake_group_message_event_v11(message=Message(command))

    with patch_session(UTILS_MODULE, session):
        with (
            patch(f"{PR_MODULE}.get_user_scores", new=AsyncMock(return_value=[score])) as get_scores,
            patch(f"{PR_MODULE}.cal_score_info"),
            patch(f"{PR_MODULE}.draw_pfm", new=AsyncMock(return_value=b"LIST")) as draw_list,
        ):
            async with app.test_matcher(matcher) as ctx:
                adapter = nonebot.get_adapter(OnebotV11Adapter)
                bot = ctx.create_bot(base=Bot, adapter=adapter)
                ctx.receive_event(bot, event)
                ctx.should_call_send(
                    event,
                    Message(
                        [
                            MessageSegment.reply(event.message_id),
                            MessageSegment.image(file=f"base64://{base64.b64encode(b'LIST').decode()}"),
                        ]
                    ),
                    result={"message_id": 1},
                )
                ctx.should_finished()

    assert get_scores.call_args.args[5:] == (include_fails, 0, 30)
    assert draw_list.call_args.args[0] == project
