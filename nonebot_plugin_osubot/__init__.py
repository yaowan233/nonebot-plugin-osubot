import re
import shutil
import urllib
import asyncio
from dataclasses import dataclass
from pathlib import Path
from random import shuffle
from typing import List, Union
from expiringdict import ExpiringDict

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment, ActionFailed
from nonebot.adapters.onebot.v11.helpers import ImageURLs
from nonebot.permission import SUPERUSER
from nonebot_plugin_guild_patch import GuildMessageEvent
from nonebot.exception import ParserExit
from nonebot.internal.params import Depends
from nonebot.params import T_State, ShellCommandArgv, CommandArg, RegexGroup
from nonebot.plugin import PluginMetadata
from nonebot.rule import ArgumentParser
from nonebot.log import logger
from nonebot import on_command, require, on_shell_command, on_regex, get_driver
from nonebot_plugin_tortoise_orm import add_model
from .draw import draw_info, draw_score, draw_map_info, draw_bmap_info, draw_bp, image2bytesio, get_score_data
from .file import download_map, map_downloaded, download_osu, download_tmp_osu, user_cache_path, save_info_pic
from .utils import NGM, GMN, mods2list
from .database.models import UserData
from .mania import generate_preview_pic, convert_mania_map, Options
from .api import osu_api, get_sayo_map_info, get_recommend, update_recommend
from .info import get_bg, bind_user_info, update_user_info
from .matcher import *
from .config import Config


require('nonebot_plugin_apscheduler')
from nonebot_plugin_apscheduler import scheduler


@dataclass
class ReviewData:
    msg_id: int
    pic_url: str
    group: int
    user: str
    id: int


review_pic_ls: List[ReviewData] = []
counter = 0
recommend_cache = ExpiringDict(1000, 60 * 60 * 12)
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
    type='application',
    homepage='https://github.com/yaowan233/nonebot-plugin-osubot',
    config=Config,
    supported_adapters={"~onebot.v11", "~qqguild"},
    extra={
        "unique_name": "osubot",
        "author": "yaowan233 <572473053@qq.com>",
        "version": "3.2.12",
    },
)

add_model('nonebot_plugin_osubot.database.models')


parser = ArgumentParser('convert', description='变换mania谱面')
parser.add_argument('--set', type=int, help='要转换的谱面的setid')
parser.add_argument('--map', type=int, help='要转换的谱面的mapid')
parser.add_argument('--fln', action='store_true', help='将谱面转换为反键')
parser.add_argument('--rate', type=float, help='谱面倍速速率')
parser.add_argument('--end_rate', type=float, help='谱面倍速速率的最大值')
parser.add_argument('--step', type=float, help='谱面倍速的step')
parser.add_argument('--od', type=float, help='改变谱面od到指定值')
parser.add_argument('--nsv', action='store_true', help='移除谱面所有sv')
parser.add_argument('--nln', action='store_true', help='移除谱面所有ln')
parser.add_argument('--gap', nargs='?', default='150', type=float, help='指定反键的间距时间，默认150ms')
parser.add_argument('--thres', nargs='?', default='100', type=float, help='指定转反键时ln转换为note的阈值，默认100ms')

convert = on_shell_command("convert", parser=parser, block=True, priority=13)


@convert.handle()
async def _(
        bot: Bot, event: Union[GroupMessageEvent, GuildMessageEvent], argv: List[str] = ShellCommandArgv()
):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + '很抱歉，频道暂不支持上传文件')
    try:
        args = parser.parse_args(argv)
    except ParserExit as e:
        if e.status == 0:
            await convert.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(
                Path(__file__).parent / 'osufile' / 'convert.jpg'))
        await convert.finish(MessageSegment.reply(event.message_id) + str(e))
        return
    options = Options(**vars(args))
    if options.map:
        sayo_map_info = await get_sayo_map_info(options.map, 1)
        options.set = sayo_map_info.data.sid
        options.sayo_info = sayo_map_info
    if not options.set:
        await convert.finish(MessageSegment.reply(event.message_id) + '请提供需要转换的谱面setid')
    if options.nln and options.fln:
        await convert.finish(MessageSegment.reply(event.message_id) + '指令矛盾！')
    osz_file = await convert_mania_map(options)
    if not osz_file:
        await convert.finish(MessageSegment.reply(event.message_id) + '未找到该地图，请检查是否搞混了mapID与setID')
    name = urllib.parse.unquote(osz_file.name)
    file_path = osz_file.absolute()
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(file_path), name=name)
    except ActionFailed:
        await convert.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            osz_file.unlink()
        except PermissionError:
            ...

info = on_command("info", aliases={'Info', 'INFO'}, block=True, priority=11)


@info.handle(parameterless=[split_msg()])
async def _info(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    day = state['day']
    data = await draw_info(user, NGM[mode], day, state['is_name'])
    await info.finish(MessageSegment.reply(event.message_id) + data)


mu = on_command("mu", aliases={'Mu', 'MU'}, block=True, priority=11)


@mu.handle(parameterless=[split_msg()])
async def _mu(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user_id = state['user']
    data = f"https://osu.ppy.sh/u/{user_id}"
    await mu.finish(MessageSegment.reply(event.message_id) + data)


recent = on_command("recent", aliases={'re', 'RE', 'Re'}, priority=11, block=True)


@recent.handle(parameterless=[split_msg()])
async def _recent(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await recent.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    data = await draw_score('recent', user, NGM[mode], [], is_name=state['is_name'])
    await recent.finish(MessageSegment.reply(event.message_id) + data)

pr = on_command("pr", priority=11, block=True, aliases={'PR', 'Pr'})


@pr.handle(parameterless=[split_msg()])
async def _pr(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await pr.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    data = await draw_score('pr', user, NGM[mode], [], is_name=state['is_name'])
    await pr.finish(MessageSegment.reply(event.message_id) + data)

score = on_command('score', priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await score.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    map_id = state['para']
    data = await get_score_data(user, NGM[mode], mapid=map_id, mods=mods, is_name=state['is_name'])
    await score.finish(MessageSegment.reply(event.message_id) + data)


bp = on_command('bp', priority=11, block=True)


@bp.handle(parameterless=[split_msg()])
async def _bp(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await bp.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    para = state['para']
    if '-' in para:
        await _pfm(state, event)
        return
    if not para.isdigit():
        await bp.finish(MessageSegment.reply(event.message_id) + '只能接受纯数字的bp参数')
    best = int(para)
    if best <= 0 or best > 100:
        await bp.finish(MessageSegment.reply(event.message_id) + '只允许查询bp 1-100 的成绩')
    data = await draw_score('bp', user, NGM[mode], best=best, mods=mods, is_name=state['is_name'])
    await bp.finish(MessageSegment.reply(event.message_id) + data)


pfm = on_command('pfm', priority=11, block=True)


@pfm.handle(parameterless=[split_msg()])
async def _pfm(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await pfm.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    para = state['para']
    ls = para.split('-')
    low, high = ls[0], ls[1]
    if not low.isdigit() or not high.isdigit():
        await pfm.finish(MessageSegment.reply(event.message_id) + '参数应为 "数字-数字"的形式!')
        return
    low, high = int(low), int(high)
    if not 0 < low < high <= 100:
        await pfm.finish(MessageSegment.reply(event.message_id) + '仅支持查询bp1-100')
    data = await draw_bp('bp', user, NGM[mode], mods, low, high, is_name=state['is_name'])
    await pfm.finish(MessageSegment.reply(event.message_id) + data)


tbp = on_command('tbp', aliases={'todaybp'}, priority=11, block=True)


@tbp.handle(parameterless=[split_msg()])
async def _tbp(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await tbp.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    day = state['day']
    data = await draw_bp('tbp', user, NGM[mode], [], day=day, is_name=state['is_name'])
    await tbp.finish(MessageSegment.reply(event.message_id) + data)


osu_map = on_command('map', priority=11, block=True)


@osu_map.handle(parameterless=[split_msg()])
async def _map(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    map_id = state['para']
    mods = state['mods']
    if not map_id:
        await osu_map.finish(MessageSegment.reply(event.message_id) + '请输入地图ID')
    elif not map_id.isdigit():
        await osu_map.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图ID')
    m = await draw_map_info(map_id, mods)
    await osu_map.finish(MessageSegment.reply(event.message_id) + m)


bmap = on_command('bmap', priority=11, block=True)


@bmap.handle(parameterless=[split_msg()])
async def _bmap(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    set_id = state['para']
    if not set_id:
        await bmap.finish(MessageSegment.reply(event.message_id) + '请输入setID')
    if not set_id.isdigit():
        await bmap.finish(MessageSegment.reply(event.message_id) + '请输入正确的setID')
        return
    m = await draw_bmap_info(set_id)
    await bmap.finish(MessageSegment.reply(event.message_id) + m)


osudl = on_command('osudl', priority=11, block=True)


@osudl.handle()
async def _osudl(bot: Bot, event: Union[GroupMessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + '很抱歉，频道暂不支持上传文件')
    setid = msg.extract_plain_text().strip()
    if not setid:
        return
    if not setid.isdigit():
        await osudl.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图ID')
    osz_path = await download_map(int(setid))
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(file_path), name=name)
    except ActionFailed:
        await osudl.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...

bind = on_command('bind', priority=11, block=True)
lock = asyncio.Lock()


@bind.handle()
async def _bind(event: Union[MessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    name = msg.extract_plain_text()
    if not name:
        await bind.finish(MessageSegment.reply(event.message_id) + '请输入您的 osuid')
    async with lock:
        if _ := await UserData.get_or_none(user_id=event.get_user_id()):
            await bind.finish(MessageSegment.reply(event.message_id) + '您已绑定，如需要解绑请输入/unbind')
        msg = await bind_user_info('bind', name, event.get_user_id(), True)
    await bind.finish(MessageSegment.reply(event.message_id) + msg)


unbind = on_command('unbind', priority=11, block=True)


@unbind.handle()
async def _unbind(event: Union[MessageEvent, GuildMessageEvent]):
    if _ := await UserData.get_or_none(user_id=event.get_user_id()):
        await UserData.filter(user_id=event.get_user_id()).delete()
        await unbind.finish(MessageSegment.reply(event.message_id) + '解绑成功！')
    else:
        await unbind.finish(MessageSegment.reply(event.message_id) + '尚未绑定，无需解绑')


update = on_command('更新模式', priority=11, aliases={'更改模式'}, block=True)


@update.handle()
async def _(event: Union[MessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    args = msg.extract_plain_text().strip()
    user = await UserData.get_or_none(user_id=event.get_user_id())
    if not user:
        await update.finish(MessageSegment.reply(event.message_id) + '该账号尚未绑定，请输入 /bind 用户名 绑定账号')
    elif not args:
        await update.finish(MessageSegment.reply(event.message_id) + '请输入需要更新内容的模式')
    if not args.isdigit():
        await update.finish(MessageSegment.reply(event.message_id) + '请输入正确的模式 0-3')
        return
    mode = int(args)
    if 0 <= mode < 4:
        await UserData.filter(user_id=event.get_user_id()).update(osu_mode=mode)
        msg = f'已将默认模式更改为 {NGM[str(mode)]}'
    else:
        msg = '请输入正确的模式 0-3'
    await update.finish(MessageSegment.reply(event.message_id) + msg)


getbg = on_command('getbg', priority=11, block=True)


@getbg.handle()
async def _get_bg(event: Union[MessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    bg_id = msg.extract_plain_text().strip()
    if not bg_id:
        msg = '请输入需要提取BG的地图ID'
    else:
        byt = await get_bg(bg_id)
        if isinstance(msg, str):
            await getbg.finish(MessageSegment.reply(event.message_id) + msg)
        msg = MessageSegment.image(byt)
    await getbg.finish(MessageSegment.reply(event.message_id) + msg)

change = on_command('倍速', priority=11, block=True)


@change.handle()
async def _(bot: Bot, event: Union[GroupMessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + '很抱歉，频道暂不支持上传文件')
    args = msg.extract_plain_text().strip().split()
    argv = ['--map']
    if not args:
        await change.finish(MessageSegment.reply(event.message_id) + '请输入需要倍速的地图mapID')
    set_id = args[0]
    if not set_id.isdigit():
        await change.finish(MessageSegment.reply(event.message_id) + '请输入正确的mapID')
    argv.append(set_id)
    if len(args) >= 2:
        argv.append('--rate')
        if '-' in args[1]:
            low, high = args[1].split('-')
            argv.extend([low, '--end_rate', high, '--step', '0.05'])
        else:
            argv.append(args[1])
    else:
        await change.finish(MessageSegment.reply(event.message_id) + '请输入倍速速率')
    args = parser.parse_args(argv)
    options = Options(**vars(args))
    if options.map:
        sayo_map_info = await get_sayo_map_info(options.map, 1)
        options.set = sayo_map_info.data.sid
        options.sayo_info = sayo_map_info
    osz_path = await convert_mania_map(options)
    if not osz_path:
        await change.finish(MessageSegment.reply(event.message_id) + '未找到该地图，请检查是否搞混了mapID与setID')
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(file_path), name=name)
    except ActionFailed:
        await change.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...

generate_full_ln = on_command('反键', priority=11, block=True)


@generate_full_ln.handle()
async def _(bot: Bot, event: Union[GroupMessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    if isinstance(event, GuildMessageEvent):
        await convert.finish(MessageSegment.reply(event.message_id) + '很抱歉，频道暂不支持上传文件')
    args = msg.extract_plain_text().strip().split()
    if not args:
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '请输入需要转ln的地图setID')
    set_id = args[0]
    if not set_id.isdigit():
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '请输入正确的setID')
    argv = ['--set', set_id, '--fln']
    if len(args) >= 2:
        argv.append('--gap')
        argv.append(args[1])
    if len(args) >= 3:
        argv.append('--thres')
        argv.append(args[2])
    args = parser.parse_args(argv)
    options = Options(**vars(args))
    osz_path = await convert_mania_map(options)
    if not osz_path:
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '未找到该地图，请检查是否搞混了mapID与setID')
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(file_path), name=name)
    except ActionFailed:
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...

generate_preview = on_command('预览', aliases={'preview'}, priority=11, block=True)


@generate_preview.handle()
async def _(event: Union[MessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    osu_id = msg.extract_plain_text().strip()
    if not osu_id or not osu_id.isdigit():
        await osudl.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图mapID')
    data = await osu_api('map', map_id=int(osu_id))
    if not data:
        await generate_preview.finish(MessageSegment.reply(event.message_id) + '未查询到该地图')
    if isinstance(data, str):
        await generate_preview.finish(MessageSegment.reply(event.message_id) + data)
    osu = await download_tmp_osu(osu_id)
    pic = await generate_preview_pic(osu)
    await generate_preview.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(pic))


generate_preview = on_command('完整预览', priority=11, block=True)


@generate_preview.handle()
async def _(event: Union[MessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    osu_id = msg.extract_plain_text().strip()
    if not osu_id or not osu_id.isdigit():
        await osudl.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图mapID')
    data = await osu_api('map', map_id=int(osu_id))
    if not data:
        await generate_preview.finish(MessageSegment.reply(event.message_id) + '未查询到该地图')
    if isinstance(data, str):
        await generate_preview.finish(MessageSegment.reply(event.message_id) + data)
    osu = await download_tmp_osu(osu_id)
    pic = await generate_preview_pic(osu, full=True)
    await generate_preview.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(pic))

update_pic = on_command('更新背景', aliases={'更改背景'}, priority=11, block=True)


@update_pic.handle(parameterless=[split_msg()])
async def _(bot: Bot, state: T_State, event: GroupMessageEvent, pic_ls: list = ImageURLs('请在指令后附上图片')):
    global counter
    if 'error' in state:
        await update_pic.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    pic_url = pic_ls[0]
    review_pic_ls.append(ReviewData(event.message_id, pic_url, event.group_id, str(user), counter))
    msg = f'收到id为{counter}来自群{event.group_id}的更新背景申请' + MessageSegment.image(pic_url)
    for superuser in get_driver().config.superusers:
        await bot.send_private_msg(user_id=int(superuser), message=msg)
    counter += 1
    await update_pic.finish(MessageSegment.reply(event.message_id) + '已收到图片，请等待审核捏~')


update = on_command('update', aliases={'更新'}, priority=11, block=True)


@update.handle(parameterless=[split_msg()])
async def _(state: T_State, event: Union[MessageEvent, GuildMessageEvent]):
    if 'error' in state:
        await update.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    path = user_cache_path / str(user) / 'icon.png'
    if path.exists():
        path.unlink()
    await update.finish(MessageSegment.reply(event.message_id) + '个人信息更新成功')

accept = on_command('同意全部', priority=11, block=True, permission=SUPERUSER)


@accept.handle()
async def _():
    for i in review_pic_ls:
        await save_info_pic(i.user, i.pic_url)
    await accept.finish('全部审核通过')


reject = on_command('拒绝', aliases={'否决'}, priority=11, block=True, permission=SUPERUSER)


@reject.handle()
async def _(bot: Bot, msg: Message = CommandArg()):
    arg = msg.extract_plain_text().strip()
    for num, i in enumerate(review_pic_ls):
        if i.id == int(arg):
            msg = MessageSegment.reply(i.msg_id) + '你的提交的图片被拒绝，请重新上传'
            await bot.send_group_msg(group_id=i.group, message=msg)
            del review_pic_ls[num]
            break
    await reject.finish(f'拒绝id{arg}成功')


recommend = on_command('recommend', aliases={'推荐', '推荐铺面', '推荐谱面'}, priority=11, block=True)


@recommend.handle(parameterless=[split_msg()])
async def _(event: Union[MessageEvent, GuildMessageEvent], state: T_State):
    if 'error' in state:
        await recommend.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    if mods == ['4K']:
        key_count = '4'
    elif mods == ['7K']:
        key_count = '7'
    else:
        key_count = '4,7'
    if mode == '1' or mode == '2':
        await recommend.finish('很抱歉，该模式暂不支持推荐')
    if not recommend_cache.get(user):
        recommend_cache[user] = set()
        await update_recommend(user)
    recommend_data = await get_recommend(user, mode, key_count)
    shuffle(recommend_data.data.list)
    if not recommend_data.data or not recommend_data.data.list:
        await recommend.finish('没有可以推荐的图哦，自己多打打喜欢玩的图吧')
    for i in recommend_data.data.list:
        if i.id not in recommend_cache[user]:
            recommend_cache[user].add(i.id)
            recommend_map = i
            break
    else:
        await recommend.finish('今天已经没有可以推荐的图啦，明天再来吧')
        return
    bid = int(re.findall('https://osu.ppy.sh/beatmaps/(.*)', recommend_map.mapLink)[0])
    map_info = await get_sayo_map_info(bid, 1)
    sid = map_info.data.sid
    for i in map_info.data.bid_data:
        if i.bid == bid:
            bg = i.bg
            break
    else:
        bg = ''
        logger.debug(f'如果看到这句话请联系作者 有问题的是{bid}, {sid}')
    s = f'推荐的铺面是{recommend_map.mapName} ⭐{round(recommend_map.difficulty, 2)}\n{"".join(recommend_map.mod)}\n' \
        f'预计pp为{round(recommend_map.predictPP, 2)}\n提升概率为{round(recommend_map.passPercent*100, 2)}%\n' \
        f'{recommend_map.mapLink}\nhttps://kitsu.moe/api/d/{sid}\nhttps://txy1.sayobot.cn/beatmaps/download/novideo/{sid}'
    await recommend.finish(MessageSegment.reply(event.message_id) +
                           MessageSegment.image(f'https://dl.sayobot.cn/beatmaps/files/{sid}/{bg}') + s)

osu_help = on_command('osuhelp', priority=11, block=True)
with open(Path(__file__).parent / 'osufile' / 'help.png', 'rb') as f:
    img1 = f.read()
with open(Path(__file__).parent / 'osufile' / 'detail.png', 'rb') as f:
    img2 = f.read()


@osu_help.handle()
async def _help(event: Union[MessageEvent, GuildMessageEvent], msg: Message = CommandArg()):
    arg = msg.extract_plain_text().strip()
    if not arg:
        await osu_help.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(img1))
    if arg == 'detail':
        await osu_help.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(img2))
    else:
        await osu_help.finish(MessageSegment.reply(event.message_id) + '呜呜，detail都打不对吗(ノ｀Д)ノ')

url_match = on_regex("https://osu.ppy.sh/beatmapsets/(.*)#")


@url_match.handle()
async def _url(event: Union[MessageEvent, GuildMessageEvent], bid: tuple = RegexGroup()):
    url_1 = "https://osu.direct/api/d/"
    url_2 = "https://txy1.sayobot.cn/beatmaps/download/novideo/"
    url_total = f"kitsu镜像站：{url_1}{bid[0]}\n小夜镜像站：{url_2}{bid[0]}"
    await url_match.finish(MessageSegment.reply(event.message_id) + url_total)


@scheduler.scheduled_job('cron', hour='0', misfire_grace_time=60)
async def update_info():
    result = await UserData.all()
    if not result:
        return
    for user in result:
        await update_user_info(user.osu_id)
    logger.info(f'已更新{len(result)}位玩家数据')


manual_update = on_command('更新数据', priority=11, block=True)


@manual_update.handle()
async def _():
    await update_info()


@scheduler.scheduled_job('cron', hour='4', day_of_week='0,4', misfire_grace_time=60)
async def delete_cached_map():
    map_path = Path('data/osu/map')
    shutil.rmtree(map_path)
    map_path.mkdir(parents=True, exist_ok=True)
    user_path = Path('data/osu/user')
    for file_path in user_path.glob('**/*'):
        if file_path.is_file() and file_path.name == 'icon.png':
            file_path.unlink()
