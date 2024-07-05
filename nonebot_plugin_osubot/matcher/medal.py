import re
import json
from pathlib import Path

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

from ..api import safe_async_get

medal_data_path = Path(__file__).parent.parent / "osufile" / "medals" / "medals.json"
with open(medal_data_path) as file:
    medal_json = json.load(file)


medal = on_command("medal", aliases={"成就"}, priority=11, block=True)


@medal.handle()
async def _(msg: Message = CommandArg()):
    name = msg.extract_plain_text()
    data = await safe_async_get(f"https://osekai.net/medals/api/public/get_medal.php?medal={name}")
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
        words += medal_data["Solution"] if medal_data["Solution"] else medal_data["Instructions"]
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
        words += f'\nhttps://osu.ppy.sh/beatmaps/packs/{medal_data["PackID"].rstrip(",,,")}'
    await (UniMessage.image(url=medal_data["Link"]) + words).send(reply_to=True)
    if medal_data["beatmaps"]:
        msg = UniMessage()
        if len(medal_data["beatmaps"]) > 5:
            medal_data["beatmaps"] = medal_data["beatmaps"][:5]
        for beatmap in medal_data["beatmaps"]:
            msg += (
                f'{beatmap["SongTitle"]} [{beatmap["DifficultyName"]}]\n{beatmap["Difficulty"]}⭐\n'
                + f'https://osu.ppy.sh/b/{beatmap["BeatmapID"]}'
            )
        await msg.send()
