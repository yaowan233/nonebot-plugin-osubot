import re
import json
from typing import List, Tuple
from pathlib import Path

from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    Message,
    MessageSegment,
    Bot,
    MessageEvent,
    GroupMessageEvent,
)
from nonebot.params import CommandArg
from ..api import safe_async_get


medal_data_path = Path(__file__).parent.parent / "osufile" / "medals" / "medals.json"
with open(medal_data_path, "r") as file:
    medal_json = json.load(file)


async def send_forward_msg(
    bot: Bot,
    event: MessageEvent,
    user_message: List[Tuple[str, str, Message]],
):
    """
    发送 forward 消息

    > 参数：
        - bot: Bot 对象
        - event: MessageEvent 对象
        - user_message: 合并消息的用户信息列表

    > 返回值：
        - 成功：返回消息发送结果
        - 失败：抛出异常
    """

    def to_json(info: Tuple[str, str, Message]):
        """
        将消息转换为 forward 消息的 json 格式
        """
        return {
            "type": "node",
            "data": {"name": info[0], "uin": info[1], "content": info[2]},
        }

    messages = [to_json(info) for info in user_message]
    if isinstance(event, GroupMessageEvent):
        return await bot.call_api(
            "send_group_forward_msg", group_id=event.group_id, messages=messages
        )
    else:
        return await bot.call_api(
            "send_private_forward_msg", user_id=event.user_id, messages=messages
        )


medal = on_command("medal", aliases={"成就"}, priority=11, block=True)


@medal.handle()
async def _(bot: Bot, event: MessageEvent, msg: Message = CommandArg()):
    name = msg.extract_plain_text()
    data = await safe_async_get(
        f"https://osekai.net/medals/api/public/get_medal.php?medal={name}"
    )
    medal_data = data.json()
    if "MedalID" not in medal_data:
        await medal.finish("没有找到欸，看看是不是名字打错了")
    words = ""
    if medal_data["Restriction"] != "NULL":
        words += f"限制模式：{medal_data['Restriction']}\n"
    words += "获得方式：\n"
    if medal_data["Name"] in medal_json:
        words += medal_json[medal_data["Name"]]["MedalSolution"]
    else:
        words += (
            medal_data["Solution"]
            if medal_data["Solution"]
            else medal_data["Instructions"]
        )
        table_regex = r"<table[^>]*>(.*?)<\/table>"
        table_match = re.search(table_regex, words, re.DOTALL)
        if table_match:
            table_text = table_match.group(1)

            # 使用正则表达式匹配并提取表格行部分
            row_regex = r"<tr[^>]*>(.*?)<\/tr>"
            rows = re.findall(row_regex, table_text, re.DOTALL)

            result = ""

            # 遍历表格行并提取单元格内容
            for row in rows:
                # 使用正则表达式匹配并提取单元格部分
                cell_regex = r"<t[hd][^>]*>(.*?)<\/t[hd]>"
                cells = re.findall(cell_regex, row, re.DOTALL)
                for cell in cells:
                    # 去除单元格内的HTML标签
                    cell_text = re.sub(r"<[^>]*>", "", cell)
                    result += cell_text + " "
                result += "\n"

            # 将提取的表格文字替换回原文中
            words = re.sub(table_regex, result, words)
    style_regex = r"<style[^>]*>(.*?)<\/style>"
    words = re.sub(style_regex, "", words)
    words = re.sub(r"<[^>]+>", "", words)
    if medal_data["PackID"]:
        words += (
            f'\nhttps://osu.ppy.sh/beatmaps/packs/{medal_data["PackID"].rstrip(",,,")}'
        )
    await medal.send(
        MessageSegment.reply(event.message_id)
        + MessageSegment.image(medal_data["Link"])
        + words
    )
    if medal_data["beatmaps"]:
        msg_ls = []
        for beatmap in medal_data["beatmaps"]:
            msg = (
                MessageSegment.image(
                    f'https://assets.ppy.sh/beatmaps/{beatmap["MapsetID"]}/covers/cover.jpg'
                )
                + f'{beatmap["SongTitle"]} [{beatmap["DifficultyName"]}]\n{beatmap["Difficulty"]}⭐\n'
                + f'https://osu.ppy.sh/b/{beatmap["BeatmapID"]}'
            )
            msg_ls.append(("推荐谱面", bot.self_id, msg))
        await send_forward_msg(bot, event, msg_ls)
