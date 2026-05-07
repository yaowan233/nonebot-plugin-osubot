import asyncio

from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from ..api import get_recommend
from ..draw.recommend import draw_recommend
from ..exceptions import NetworkError
from ..utils import NGM

recommend = on_command("推荐", priority=11, block=True, aliases={"recommend", "推荐铺面", "推荐谱面"})


@recommend.handle(parameterless=[split_msg()])
async def _(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    user = state["user"]
    mode = state["mode"]
    api_task = asyncio.create_task(get_recommend(user, mode))
    done, _ = await asyncio.wait([api_task], timeout=5)
    if not done:
        await UniMessage.text("正在获取推荐谱面，请稍候...").send(reply_to=True)
    try:
        recommend_data = await api_task
    except NetworkError as e:
        await UniMessage.text(f"在查找用户：{state['username']} {NGM[mode]}模式 stable模式下时 {str(e)}").send(
            reply_to=True
        )
        return
    if not recommend_data.recommendations:
        await UniMessage.text("该玩家pp过低，暂无推荐\n可以试试多打打图提升pp后再来哦").send(reply_to=True)
        return
    username = state.get("username", str(user))
    avatar_url = f"https://a.ppy.sh/{user}"
    pic = await draw_recommend(recommend_data, username, avatar_url)
    await UniMessage.image(raw=pic).send(reply_to=True)
