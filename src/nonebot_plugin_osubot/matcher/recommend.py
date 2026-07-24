import asyncio

from nonebot import on_command
from nonebot.typing import T_State
from nonebot_plugin_alconna import UniMessage

from .utils import split_msg
from ..api import get_recommend
from ..draw.recommend import draw_recommend
from ..exceptions import NetworkError
from ..utils import NGM

RECOMMEND_TARGET_ALIASES = {
    "farm": "farm",
    "pp": "farm",
    "吃分": "farm",
    "mixed": "mixed",
    "mix": "mixed",
    "all": "mixed",
    "overall": "mixed",
    "综合": "mixed",
    "总和": "mixed",
    "全部": "mixed",
    "推荐": "mixed",
    "balanced": "balanced",
    "balance": "balanced",
    "normal": "balanced",
    "普通": "balanced",
    "peak": "peak",
    "hard": "peak",
    "harder": "peak",
    "difficult": "peak",
    "challenge": "peak",
    "难一点": "peak",
    "更难": "peak",
    "高难": "peak",
    "冲分": "peak",
    "style": "style",
    "practice": "style",
    "train": "style",
    "training": "style",
    "风格": "style",
    "练习": "style",
    "练图": "style",
    "练习推荐": "style",
}


def _recommend_target_from_state(state: T_State) -> str:
    raw = str(state.get("username") or "").strip().lower()
    target = RECOMMEND_TARGET_ALIASES.get(raw)
    if target:
        state["user"] = state.get("bound_user", state.get("user", 0))
        state["username"] = state.get("bound_username", "")
        state.pop("error", None)
        return target
    return "mixed"


recommend = on_command("推荐", priority=11, block=True, aliases={"recommend", "推荐铺面", "推荐谱面"})


@recommend.handle(parameterless=[split_msg()])
async def _(state: T_State):
    target = _recommend_target_from_state(state)
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    user = state["user"]
    mode = state["mode"]
    api_task = asyncio.create_task(get_recommend(user, mode, target))
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
        await UniMessage.text("暂时没有找到可推荐的谱面，已加入更新队列\n请明天再来查看推荐吧").send(reply_to=True)
        return
    username = state.get("username", str(user))
    avatar_url = f"https://a.ppy.sh/{user}"
    pic = await draw_recommend(recommend_data, username, avatar_url)
    await UniMessage.image(raw=pic).send(reply_to=True)
