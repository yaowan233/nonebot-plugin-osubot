import asyncio
import datetime
from io import BytesIO

from PIL import Image, ImageDraw
from nonebot.params import T_State
from nonebot import Bot, on_command
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_session import SessionId, SessionIdType
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from ..utils import NGM
from .utils import split_msg
from ..file import get_projectimg
from ..draw.utils import draw_fillet
from ..draw.static import Torus_Regular_25
from ..database.models import InfoData, UserData

group_pp_rank = on_command("群内排名", priority=11, block=True)


@group_pp_rank.handle(parameterless=[split_msg()])
async def _(state: T_State, bot: Bot, session_id: str = SessionId(SessionIdType.GROUP)):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
    mode = state["mode"]
    group_id = session_id
    if bot.adapter.get_name() == "OneBot V11":
        group_member = await bot.get_group_member_list(group_id=group_id)
        user_id_ls = [str(i["user_id"]) for i in group_member]
    elif bot.adapter.get_name() == "Satori":
        group_member = await bot.guild_member_list(guild_id=group_id)
        user_id_ls = [i.user.id for i in group_member]
    else:
        raise NotImplementedError
    async with get_session() as session:
        binded_id = (await session.scalars(select(UserData.osu_id).where(UserData.user_id.in_(user_id_ls)))).all()
        info_ls = (
            await session.scalars(
                select(InfoData)
                .where(
                    InfoData.osu_id.in_(binded_id),
                    InfoData.osu_mode == int(mode),
                    InfoData.date == datetime.date.today(),
                )
                .order_by(InfoData.pp.desc())
            )
        ).all()
        icon_ls = [f"https://a.ppy.sh/{info.osu_id}" for info in info_ls]
        tasks = [get_projectimg(i) for i in icon_ls]
        icon_ls = await asyncio.gather(*tasks)
        draw_len = len([i for i in info_ls if i.pp >= 100])
        img = Image.new("RGBA", (1200, 85 + 82 * draw_len), (35, 42, 34, 255))
        draw = ImageDraw.Draw(img)
        draw.text((40, 10), f"{NGM[mode]}模式群内排名", font=Torus_Regular_25, fill=(255, 255, 255, 255))
        draw.text((880, 10), "pp", font=Torus_Regular_25, fill=(255, 255, 255, 255))
        draw.text((960, 10), "全球排名", font=Torus_Regular_25, fill=(255, 255, 255, 255))
        for index, (info, icon) in enumerate(zip(info_ls, icon_ls)):
            if info.pp < 100:
                continue
            draw.rounded_rectangle(
                (20, 55 + 82 * index, 1180, 45 + 82 * (index + 1)),
                radius=10,
                fill=(58, 70, 57, 255),
            )
            icon_img = Image.open(icon).convert("RGBA").resize((63, 63))
            icon_img = draw_fillet(icon_img, 10)
            img.alpha_composite(icon_img, (100, 60 + 82 * index))
            for user in group_member:
                if await session.scalar(
                    select(UserData).where(UserData.user_id == str(user["user_id"]), UserData.osu_id == info.osu_id)
                ):
                    name = user["card"] or user.get("nickname", "")
                    break
            else:
                raise Exception("这不可能发生的")
            draw.text(
                (43, 70 + 82 * index),
                f"#{index + 1}",
                font=Torus_Regular_25,
                fill=(255, 255, 255, 255),
            )
            draw.text(
                (180, 70 + 82 * index),
                name,
                font=Torus_Regular_25,
                fill=(166, 199, 163, 255),
            )
            draw.text(
                (850, 70 + 82 * index),
                f"{int(info.pp)}pp",
                font=Torus_Regular_25,
                fill=(255, 255, 255, 255),
            )
            draw.text(
                (980, 70 + 82 * index),
                f"{info.g_rank}",
                font=Torus_Regular_25,
                fill=(255, 255, 255, 255),
            )

    byt = BytesIO()
    img.save(byt, "png")
    await UniMessage.image(raw=byt).send(reply_to=True)
