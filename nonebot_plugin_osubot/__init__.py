import shutil
import urllib
from pathlib import Path
from typing import List, Union

from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageSegment,
    ActionFailed,
)
from nonebot.exception import ParserExit
from nonebot.params import ShellCommandArgv, CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import ArgumentParser
from nonebot.log import logger
from nonebot import on_command, require, on_shell_command
from nonebot_plugin_tortoise_orm import add_model

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_guild_patch")
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_guild_patch import GuildMessageEvent
from .draw import (
    draw_info,
    draw_score,
    draw_map_info,
    draw_bmap_info,
    draw_bp,
    image2bytesio,
    get_score_data,
)
from .file import (
    download_map,
    download_osu,
    download_tmp_osu,
    user_cache_path,
    save_info_pic,
)
from .schema import Score
from .utils import NGM, GMN, mods2list
from .database.models import UserData
from .mania import generate_preview_pic, convert_mania_map, Options
from .api import osu_api, get_sayo_map_info, get_recommend, update_recommend
from .info import get_bg, bind_user_info, update_user_info
from .config import Config
from .matcher import *
from .matcher.utils import split_msg


usage = "发送/osuhelp 查看帮助"
detail_usage = """以下<>内是必填内容，()内是选填内容，user可以是用户名也可以@他人，mode为0-3的一个数字
/info (user)(:mode)
/re (user)(:mode)
/score <mapid>(:mode)(+mods)
/bp (user) <num> (:mode)(+mods)
/pfm (user) <min>-<max> (:mode)(+mods)
/tbp (user) (:mode)
/map <mapid> (+mods)
/倍速 <setid> (rate)-(rate)
/反键 <mapid> (gap) (ln_as_hit_thres)
其中gap为ln的间距默认为150 (ms)
ln_as_hit_thres为ln转为note的阈值默认为100 (ms)
rate可为任意小数"""

__plugin_meta__ = PluginMetadata(
    name="OSUBot",
    description="OSU查分插件",
    usage=usage,
    type="application",
    homepage="https://github.com/yaowan233/nonebot-plugin-osubot",
    config=Config,
    supported_adapters={"~onebot.v11", "~red"},
    extra={
        "unique_name": "osubot",
        "author": "yaowan233 <572473053@qq.com>",
    },
)

add_model("nonebot_plugin_osubot.database.models")


parser = ArgumentParser("convert", description="变换mania谱面")
parser.add_argument("--set", type=int, help="要转换的谱面的setid")
parser.add_argument("--map", type=int, help="要转换的谱面的mapid")
parser.add_argument("--fln", action="store_true", help="将谱面转换为反键")
parser.add_argument("--rate", type=float, help="谱面倍速速率")
parser.add_argument("--end_rate", type=float, help="谱面倍速速率的最大值")
parser.add_argument("--step", type=float, help="谱面倍速的step")
parser.add_argument("--od", type=float, help="改变谱面od到指定值")
parser.add_argument("--nsv", action="store_true", help="移除谱面所有sv")
parser.add_argument("--nln", action="store_true", help="移除谱面所有ln")
parser.add_argument(
    "--gap", nargs="?", default="150", type=float, help="指定反键的间距时间，默认150ms"
)
parser.add_argument(
    "--thres", nargs="?", default="100", type=float, help="指定转反键时ln转换为note的阈值，默认100ms"
)

convert = on_shell_command("convert", parser=parser, block=True, priority=13)


@convert.handle()
async def _(
    bot: Bot,
    event: Union[GroupMessageEvent, GuildMessageEvent],
    argv: List[str] = ShellCommandArgv(),
):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + "很抱歉，频道暂不支持上传文件")
    try:
        args = parser.parse_args(argv)
    except ParserExit as e:
        if e.status == 0:
            await convert.finish(
                MessageSegment.reply(event.message_id)
                + MessageSegment.image(
                    Path(__file__).parent / "osufile" / "convert.jpg"
                )
            )
        await convert.finish(MessageSegment.reply(event.message_id) + str(e))
        return
    options = Options(**vars(args))
    if options.map:
        sayo_map_info = await get_sayo_map_info(options.map, 1)
        options.set = sayo_map_info.data.sid
        options.sayo_info = sayo_map_info
    if not options.set:
        await convert.finish(MessageSegment.reply(event.message_id) + "请提供需要转换的谱面setid")
    if options.nln and options.fln:
        await convert.finish(MessageSegment.reply(event.message_id) + "指令矛盾！")
    osz_file = await convert_mania_map(options)
    if not osz_file:
        await convert.finish(
            MessageSegment.reply(event.message_id) + "未找到该地图，请检查是否搞混了mapID与setID"
        )
    name = urllib.parse.unquote(osz_file.name)
    file_path = osz_file.absolute()
    try:
        await bot.upload_group_file(
            group_id=event.group_id, file=str(file_path), name=name
        )
    except ActionFailed:
        await convert.finish(
            MessageSegment.reply(event.message_id) + "上传文件失败，可能是群空间满或没有权限导致的"
        )
    finally:
        try:
            osz_file.unlink()
        except PermissionError:
            ...


osudl = on_command("osudl", priority=11, block=True)


@osudl.handle()
async def _osudl(
    bot: Bot,
    event: Union[GroupMessageEvent, GuildMessageEvent],
    msg: Message = CommandArg(),
):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + "很抱歉，频道暂不支持上传文件")
    setid = msg.extract_plain_text().strip()
    if not setid:
        return
    if not setid.isdigit():
        await osudl.finish(MessageSegment.reply(event.message_id) + "请输入正确的地图ID")
    osz_path = await download_map(int(setid))
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await bot.upload_group_file(
            group_id=event.group_id, file=str(file_path), name=name
        )
    except ActionFailed:
        await osudl.finish(
            MessageSegment.reply(event.message_id) + "上传文件失败，可能是群空间满或没有权限导致的"
        )
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...


change = on_command("倍速", priority=11, block=True)


@change.handle()
async def _(
    bot: Bot,
    event: Union[GroupMessageEvent, GuildMessageEvent],
    msg: Message = CommandArg(),
):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + "很抱歉，频道暂不支持上传文件")
    args = msg.extract_plain_text().strip().split()
    argv = ["--map"]
    if not args:
        await change.finish(MessageSegment.reply(event.message_id) + "请输入需要倍速的地图mapID")
    set_id = args[0]
    if not set_id.isdigit():
        await change.finish(MessageSegment.reply(event.message_id) + "请输入正确的mapID")
    argv.append(set_id)
    if len(args) >= 2:
        argv.append("--rate")
        if "-" in args[1]:
            low, high = args[1].split("-")
            argv.extend([low, "--end_rate", high, "--step", "0.05"])
        else:
            argv.append(args[1])
    else:
        await change.finish(MessageSegment.reply(event.message_id) + "请输入倍速速率")
    args = parser.parse_args(argv)
    options = Options(**vars(args))
    if options.map:
        sayo_map_info = await get_sayo_map_info(options.map, 1)
        options.set = sayo_map_info.data.sid
        options.sayo_info = sayo_map_info
    osz_path = await convert_mania_map(options)
    if not osz_path:
        await change.finish(
            MessageSegment.reply(event.message_id) + "未找到该地图，请检查是否搞混了mapID与setID"
        )
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await bot.upload_group_file(
            group_id=event.group_id, file=str(file_path), name=name
        )
    except ActionFailed:
        await change.finish(
            MessageSegment.reply(event.message_id) + "上传文件失败，可能是群空间满或没有权限导致的"
        )
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...


generate_full_ln = on_command("反键", priority=11, block=True)


@generate_full_ln.handle()
async def _(
    bot: Bot,
    event: Union[GroupMessageEvent, GuildMessageEvent],
    msg: Message = CommandArg(),
):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + "很抱歉，频道暂不支持上传文件")
    args = msg.extract_plain_text().strip().split()
    if not args:
        await generate_full_ln.finish(
            MessageSegment.reply(event.message_id) + "请输入需要转ln的地图setID"
        )
    set_id = args[0]
    if not set_id.isdigit():
        await generate_full_ln.finish(
            MessageSegment.reply(event.message_id) + "请输入正确的setID"
        )
    argv = ["--set", set_id, "--fln"]
    if len(args) >= 2:
        argv.append("--gap")
        argv.append(args[1])
    if len(args) >= 3:
        argv.append("--thres")
        argv.append(args[2])
    args = parser.parse_args(argv)
    options = Options(**vars(args))
    osz_path = await convert_mania_map(options)
    if not osz_path:
        await generate_full_ln.finish(
            MessageSegment.reply(event.message_id) + "未找到该地图，请检查是否搞混了mapID与setID"
        )
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await bot.upload_group_file(
            group_id=event.group_id, file=str(file_path), name=name
        )
    except ActionFailed:
        await generate_full_ln.finish(
            MessageSegment.reply(event.message_id) + "上传文件失败，可能是群空间满或没有权限导致的"
        )
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...


@scheduler.scheduled_job("cron", hour="0", misfire_grace_time=60)
async def update_info():
    result = await UserData.all()
    if not result:
        return
    for user in result:
        await update_user_info(user.osu_id)
    logger.info(f"已更新{len(result)}位玩家数据")


@scheduler.scheduled_job("cron", hour="4", day_of_week="0,4", misfire_grace_time=60)
async def delete_cached_map():
    map_path = Path("data/osu/map")
    shutil.rmtree(map_path)
    map_path.mkdir(parents=True, exist_ok=True)
    user_path = Path("data/osu/user")
    for file_path in user_path.glob("**/*"):
        if file_path.is_file() and file_path.name in ("icon.png", "icon.gif"):
            file_path.unlink()
