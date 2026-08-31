import re

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot_plugin_alconna import UniMessage
from nonebot.internal.adapter import Event, Message
from nonebot_plugin_orm import get_session
from sqlalchemy import select, update

from ..api import get_server
from ..bindings import get_binding_spec
from ..server import ModeVariant
from ..utils import GMN, NGM

update_mode = on_command("更新模式", aliases={"mode"}, priority=11, block=True)


@update_mode.handle()
async def _(event: Event, mode: Message = CommandArg()):
    raw = mode.extract_plain_text().strip().replace("：", ":").replace("＆", "&")
    server = get_server("osu")
    for alias in re.findall(r"&(\w+)", raw):
        try:
            server = get_server(alias)
        except ValueError:
            continue
        raw = re.sub(rf"&{re.escape(alias)}\b", "", raw).strip()
    # 兼容 /mode:4 的紧贴冒号写法
    mode_input = raw.lstrip(":").strip()
    uid = event.get_user_id()
    binding_spec = get_binding_spec(server.id)

    if not binding_spec.stores_default_mode:
        await UniMessage.text(f"{server.label} 暂不保存默认模式，请在查询时显式指定模式").finish(reply_to=True)

    async with get_session() as session:
        user = await session.scalar(select(binding_spec.model).where(binding_spec.model.user_id == uid))
        if not user:
            await UniMessage.text(binding_spec.missing_message).finish(reply_to=True)
        if not mode_input:
            current = NGM[str(user.osu_mode)]
            current_label = GMN[current] if binding_spec.friendly_mode_labels else current
            special_modes = any(mode.variant != ModeVariant.STANDARD for mode in server.descriptor.modes)
            help_text = "可使用 /mode o、t、c、m（或完整模式名）修改"
            if special_modes:
                help_text += "；4/5/6/8 对应 RX std / RX taiko / RX catch / AP std"
            await UniMessage.text(
                f"当前{binding_spec.default_mode_subject}默认模式为 {current_label}（{user.osu_mode}）\n{help_text}"
            ).finish(reply_to=True)
        try:
            parsed = server.parse_mode(mode_input).legacy_key
        except ValueError:
            special_modes = any(mode.variant != ModeVariant.STANDARD for mode in server.descriptor.modes)
            msg = "请输入正确的模式：std、taiko、catch、mania，或数字 0-3"
            if special_modes:
                msg += "（该服务器还支持 4=RX std 5=RX taiko 6=RX catch 8=AP std）"
        else:
            await session.execute(
                update(binding_spec.model).where(binding_spec.model.user_id == uid).values(osu_mode=int(parsed))
            )
            await session.commit()
            mode_label = GMN[NGM[parsed]] if binding_spec.friendly_mode_labels else NGM[parsed]
            msg = f"已将{binding_spec.default_mode_subject}默认模式更改为 {mode_label}（{parsed}）"
    await UniMessage.text(msg).finish(reply_to=True)
