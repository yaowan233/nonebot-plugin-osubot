from nonebot import on_command
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage
from nonebot.internal.adapter import Event, Message
from nonebot_plugin_orm import get_session
from sqlalchemy import select, update

from ..utils import NGM, GMN, parse_mode
from ..database import UserData, G0v0UserData

update_mode = on_command("更新模式", aliases={"mode"}, priority=11, block=True)


@update_mode.handle()
async def _(event: Event, mode: Message = CommandArg()):
    raw = mode.extract_plain_text().strip().replace("：", ":").replace("＆", "&")
    source = "osu"
    if "&gu" in raw:
        source = "g0v0"
        raw = raw.replace("&gu", "").strip()
    elif "&sb" in raw:
        raw = raw.replace("&sb", "").strip()
    # 兼容 /mode:4 的紧贴冒号写法
    mode_input = raw.lstrip(":").strip()
    uid = event.get_user_id()

    async with get_session() as session:
        if source == "g0v0":
            user = await session.scalar(select(G0v0UserData).where(G0v0UserData.user_id == uid))
            if not user:
                await UniMessage.text("该账号尚未绑定 g0v0 服务器，请输入 /gubind 用户名 绑定账号").finish(
                    reply_to=True
                )
            if not mode_input:
                current = NGM[str(user.osu_mode)]
                await UniMessage.text(
                    f"当前 g0v0 默认模式为 {GMN[current]}（{user.osu_mode}）\n"
                    "可使用 /mode o、t、c、m 或数字 0-8 修改；4/5/6/8 对应 RX std / RX taiko / RX catch / AP std"
                ).finish(reply_to=True)
            parsed = parse_mode(mode_input, allow_special=True)
            if parsed is not None:
                await session.execute(
                    update(G0v0UserData).where(G0v0UserData.user_id == uid).values(osu_mode=int(parsed))
                )
                await session.commit()
                msg = f"已将 g0v0 默认模式更改为 {GMN[NGM[parsed]]}（{parsed}）"
            else:
                msg = (
                    "请输入正确的模式：std、taiko、catch、mania，或数字 0-3"
                    "（g0v0 还支持 4=RX std 5=RX taiko 6=RX catch 8=AP std）"
                )
        else:
            user = await session.scalar(select(UserData).where(UserData.user_id == uid))
            if not user:
                await UniMessage.text("该账号尚未绑定，请输入 /bind 用户名 绑定账号").finish(reply_to=True)
            if not mode_input:
                await UniMessage.text(
                    f"当前默认模式为 {NGM[str(user.osu_mode)]}（{user.osu_mode}）\n"
                    "可使用 /mode o、t、c、m（或完整模式名）修改"
                ).finish(reply_to=True)
            parsed = parse_mode(mode_input)
            if parsed is not None:
                await session.execute(update(UserData).where(UserData.user_id == uid).values(osu_mode=int(parsed)))
                await session.commit()
                msg = f"已将默认模式更改为 {NGM[parsed]}（{parsed}）"
            else:
                msg = "请输入正确的模式：std、taiko、catch、mania，或数字 0-3"
    await UniMessage.text(msg).finish(reply_to=True)
