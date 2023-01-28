import asyncio
import os
import urllib
from asyncio.tasks import Task
from pathlib import Path
from typing import List

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment, ActionFailed
from nonebot.exception import ParserExit
from nonebot.internal.params import Depends
from nonebot.params import T_State, ShellCommandArgv, CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import ArgumentParser
from nonebot.log import logger
from nonebot import on_command, require, on_shell_command
from nonebot_plugin_tortoise_orm import add_model
from .draw import draw_info, draw_score, best_pfm, map_info, bmap_info, bindinfo, get_map_bg
from .file import download_map, map_downloaded
from .utils import GM, GMN, update_user_info
from .database.models import UserData
from .mania import generate_preview_pic, convert_mania_map, Options
from .api import osu_api


require('nonebot_plugin_apscheduler')

from nonebot_plugin_apscheduler import scheduler


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
    extra={
        "unique_name": "osubot",
        "author": "yaowan233 <572473053@qq.com>",
        "version": "0.12.1",
    },
)

add_model('nonebot_plugin_osubot.database.models')


def split_msg():
    async def dependency(event: MessageEvent, state: T_State, msg: Message = CommandArg()):
        qq = event.user_id
        for msg_seg in event.message:
            if msg_seg.type == "at":
                qq = str(msg_seg.data.get("qq", ""))
        user_data = await UserData.get_or_none(user_id=qq)
        if not user_data:
            state['error'] = '该账号尚未绑定，请输入 /bind 用户名 绑定账号'
            return
        user = user_data.osu_id
        mode = str(user_data.osu_mode)
        mods = []
        arg = msg.extract_plain_text().strip()
        mode_index = max(arg.find(':'), arg.find('：'))
        mods_index = arg.find('+')
        # 没有:与+时
        if max(mode_index, mods_index) < 0:
            para = arg
            state['full_para'] = para.strip()
        else:
            # 只有+时
            if mode_index < 0:
                index = mods_index
                mods = mods2list(arg[index + 1:].strip())
            # 只有:时
            elif mods_index < 0:
                index = mode_index
                mode = arg[index + 1:]
            # 都有时
            else:
                index = min(mode_index, mods_index)
                mode = arg[mode_index + 1: mods_index]
                mods = mods2list(arg[mods_index + 1:].strip())
            para = arg[:index].strip()
            state['full_para'] = para.strip()
        # 分出user和参数
        if para.find(' ') > 0 and state['_prefix']['command'][0] not in ('pr', 're', 'info', 'tbp', 'recent'):
            user = para[:para.rfind(' ')]
            para = para[para.rfind(' ') + 1:]
        elif para.find(' ') > 0 and state['_prefix']['command'][0] in ('pr', 're', 'info', 'tbp', 'recent'):
            user = para
        if not mode.isdigit() and (int(mode) < 0 or int(mode) > 3):
            state['err'] = '模式应为0-3的数字！'
        state['para'] = para.strip()
        state['user'] = user
        state['mode'] = int(mode)
        state['mods'] = mods
    return Depends(dependency)


parser = ArgumentParser('convert', description='变换mania谱面')
parser.add_argument('set', type=int, help='要转换的谱面的setid')
parser.add_argument('--set', '-s', type=int, help='要转换的谱面的setid')
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
        bot: Bot, event: GroupMessageEvent, argv: List[str] = ShellCommandArgv()
):
    try:
        args = parser.parse_args(argv)
    except ParserExit as e:
        if e.status == 0:
            await convert.finish(MessageSegment.reply(event.message_id) + parser.format_help())
        await convert.finish(MessageSegment.reply(event.message_id) + str(e))
        return
    options = Options(**vars(args))
    if not options.set:
        await convert.finish(MessageSegment.reply(event.message_id) + '请提供需要转换的谱面setid')
    if options.nln and options.fln:
        await convert.finish(MessageSegment.reply(event.message_id) + '指令矛盾！')
    osz_file = await convert_mania_map(options)
    if not osz_file:
        await change.finish(MessageSegment.reply(event.message_id) + '未找到该地图，请检查是否搞混了mapID与setID')
    name = urllib.parse.unquote(osz_file.name)
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(osz_file.absolute()), name=name)
    except ActionFailed:
        await convert.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            os.remove(osz_file)
        except PermissionError:
            ...

info = on_command("info", block=True, priority=11)


@info.handle(parameterless=[split_msg()])
async def _info(state: T_State, event: MessageEvent):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    data = await draw_info(user, GM[mode])
    await info.finish(MessageSegment.reply(event.message_id) + data)


recent = on_command("recent", aliases={'re', 'RE', 'Re'}, priority=11, block=True)


@recent.handle(parameterless=[split_msg()])
async def _recent(state: T_State, event: MessageEvent):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['full_para'] if state['full_para'] else state['user']
    mode = state['mode']
    data = await draw_score('recent', user, GM[mode], [])
    await recent.finish(MessageSegment.reply(event.message_id) + data)

pr = on_command("pr", priority=11, block=True, aliases={'PR', 'Pr'})


@pr.handle(parameterless=[split_msg()])
async def _pr(state: T_State, event: MessageEvent):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['full_para'] if state['full_para'] else state['user']
    mode = state['mode']
    data = await draw_score('pr', user, GM[mode], [])
    await recent.finish(MessageSegment.reply(event.message_id) + data)

score = on_command('score', priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(state: T_State, event: MessageEvent):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    map_id = state['para']
    data = await draw_score('score', user, GM[mode], mapid=map_id, mods=mods)
    await score.finish(MessageSegment.reply(event.message_id) + data)


bp = on_command('bp', priority=11, block=True)


@bp.handle(parameterless=[split_msg()])
async def _bp(state: T_State, event: MessageEvent):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    best = state['para']
    if not best.isdigit():
        await bp.finish(MessageSegment.reply(event.message_id) + '只能接受纯数字的bp参数')
    best = int(best)
    if best <= 0 or best > 100:
        await bp.finish(MessageSegment.reply(event.message_id) + '只允许查询bp 1-100 的成绩')
    data = await draw_score('bp', user, GM[mode], best=best, mods=mods)
    await bp.finish(MessageSegment.reply(event.message_id) + data)


pfm = on_command('pfm', priority=11, block=True)


@pfm.handle(parameterless=[split_msg()])
async def _pfm(state: T_State, event: MessageEvent):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
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
    data = await best_pfm('bp', user, GM[mode], mods, low, high)
    await pfm.finish(MessageSegment.reply(event.message_id) + data)


tbp = on_command('tbp', aliases={'todaybp'}, priority=11, block=True)


@tbp.handle(parameterless=[split_msg()])
async def _tbp(state: T_State, event: MessageEvent):
    if 'error' in state:
        await info.finish(MessageSegment.reply(event.message_id) + state['error'])
    user = state['full_para'] if state['full_para'] else state['user']
    mode = state['mode']
    data = await best_pfm('tbp', user, GM[mode], [])
    await tbp.finish(MessageSegment.reply(event.message_id) + data)


osu_map = on_command('map', priority=11, block=True)


@osu_map.handle(parameterless=[split_msg()])
async def _map(state: T_State, event: MessageEvent):
    map_id = state['para']
    mods = state['mods']
    if not map_id:
        await osu_map.finish(MessageSegment.reply(event.message_id) + '请输入地图ID')
    elif not map_id.isdigit():
        await osu_map.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图ID')
    m = await map_info(map_id, mods)
    await osu_map.finish(MessageSegment.reply(event.message_id) + m)


bmap = on_command('bmap', priority=11, block=True)


@bmap.handle(parameterless=[split_msg()])
async def _bmap(state: T_State, event: MessageEvent):
    set_id = state['para']
    if not set_id:
        await bmap.finish(MessageSegment.reply(event.message_id) + '请输入setID')
    if not set_id.isdigit():
        await bmap.finish(MessageSegment.reply(event.message_id) + '请输入正确的setID')
        return
    m = await bmap_info(set_id)
    await bmap.finish(MessageSegment.reply(event.message_id) + m)


osudl = on_command('osudl', priority=11, block=True)


@osudl.handle()
async def _osudl(bot: Bot, event: GroupMessageEvent, msg: Message = CommandArg()):
    setid = msg.extract_plain_text().strip()
    if not setid:
        return
    if not setid.isdigit():
        await osudl.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图ID')
    filepath = await download_map(int(setid))
    name = urllib.parse.unquote(filepath.name)
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(filepath.absolute()), name=name)
    except ActionFailed:
        await osudl.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            os.remove(filepath)
        except PermissionError:
            ...

bind = on_command('bind', priority=11, block=True)


@bind.handle()
async def _bind(event: MessageEvent, msg: Message = CommandArg()):
    name = msg.extract_plain_text()
    if not name:
        await bind.finish(MessageSegment.reply(event.message_id) + '请输入您的 osuid')
    if _ := await UserData.get_or_none(user_id=event.get_user_id()):
        await bind.finish(MessageSegment.reply(event.message_id) + '您已绑定，如需要解绑请输入/unbind')
    msg = await bindinfo('bind', name, event.get_user_id())
    await bind.finish(MessageSegment.reply(event.message_id) + msg)


unbind = on_command('unbind', priority=11, block=True)


@unbind.handle()
async def _unbind(event: MessageEvent):
    if _ := await UserData.get_or_none(user_id=event.get_user_id()):
        await UserData.filter(user_id=event.get_user_id()).delete()
        await unbind.finish(MessageSegment.reply(event.message_id) + '解绑成功！')
    else:
        await unbind.finish(MessageSegment.reply(event.message_id) + '尚未绑定，无需解绑')


update = on_command('更新模式', priority=11, block=True)


@update.handle()
async def _(event: MessageEvent, msg: Message = CommandArg()):
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
        msg = f'已将默认模式更改为 {GM[mode]}'
    else:
        msg = '请输入正确的模式 0-3'
    await update.finish(MessageSegment.reply(event.message_id) + msg)


getbg = on_command('getbg', priority=11, block=True)


@getbg.handle()
async def _get_bg(event: MessageEvent, msg: Message = CommandArg()):
    bg_id = msg.extract_plain_text().strip()
    if not bg_id:
        msg = '请输入需要提取BG的地图ID'
    else:
        msg = await get_map_bg(bg_id)
    await getbg.finish(MessageSegment.reply(event.message_id) + msg)

change = on_command('倍速', priority=11, block=True)


@change.handle()
async def _(bot: Bot, event: GroupMessageEvent, msg: Message = CommandArg()):
    args = msg.extract_plain_text().strip().split()
    argv = ['--set']
    if not args:
        await change.finish(MessageSegment.reply(event.message_id) + '请输入需要倍速的地图setID')
    set_id = args[0]
    if not set_id.isdigit():
        await change.finish(MessageSegment.reply(event.message_id) + '请输入正确的setID')
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
    osz_file = await convert_mania_map(options)
    if not osz_file:
        await change.finish(MessageSegment.reply(event.message_id) + '未找到该地图，请检查是否搞混了mapID与setID')
    name = urllib.parse.unquote(osz_file.name)
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(osz_file.absolute()), name=name)
    except ActionFailed:
        await change.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            os.remove(osz_file)
        except PermissionError:
            ...

generate_full_ln = on_command('反键', priority=11, block=True)


@generate_full_ln.handle()
async def _(bot: Bot, event: GroupMessageEvent, msg: Message = CommandArg()):
    args = msg.extract_plain_text().strip().split()
    argv = ['--fln', '--set']
    if not args:
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '请输入需要转ln的地图setID')
    set_id = args[0]
    if not set_id.isdigit():
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '请输入正确的setID')
    argv.append(set_id)
    if len(args) >= 2:
        argv.append('--gap')
        argv.append(args[1])
    if len(args) >= 3:
        argv.append('--thres')
        argv.append(args[2])
    args = parser.parse_args(argv)
    options = Options(**vars(args))
    osz_file = await convert_mania_map(options)
    if not osz_file:
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '未找到该地图，请检查是否搞混了mapID与setID')
    name = urllib.parse.unquote(osz_file.name)
    try:
        await bot.upload_group_file(group_id=event.group_id, file=str(osz_file.absolute()), name=name)
    except ActionFailed:
        await generate_full_ln.finish(MessageSegment.reply(event.message_id) + '上传文件失败，可能是群空间满或没有权限导致的')
    finally:
        try:
            os.remove(osz_file)
        except PermissionError:
            ...

generate_preview = on_command('预览', aliases={'preview'}, priority=11, block=True)


@generate_preview.handle()
async def _(event: MessageEvent, msg: Message = CommandArg()):
    osu_id = msg.extract_plain_text().strip()
    if not osu_id or not osu_id.isdigit():
        await osudl.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图mapID')
    data = await osu_api('map', map_id=int(osu_id))
    if not data:
        await generate_preview.finish(MessageSegment.reply(event.message_id) + '未查询到该地图')
    if isinstance(data, str):
        await generate_preview.finish(MessageSegment.reply(event.message_id) + data)
    setid: int = data['beatmapset_id']
    dirpath = await map_downloaded(str(setid))
    osu = dirpath / f"{osu_id}.osu"
    pic = await generate_preview_pic(osu)
    await generate_preview.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(pic))

osu_help = on_command('osuhelp', priority=11, block=True)


@osu_help.handle()
async def _help(event: MessageEvent, msg: Message = CommandArg()):
    arg = msg.extract_plain_text().strip()
    if not arg:
        await osu_help.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(Path(__file__).parent / 'osufile' / 'help.png'))
    if arg == 'detail':
        await osu_help.finish(MessageSegment.reply(event.message_id) + detail_usage)
    else:
        await osu_help.finish(MessageSegment.reply(event.message_id) + '呜呜，detail都打不对吗(ノ｀Д)ノ')


@scheduler.scheduled_job('cron', hour='0')
async def update_info():
    tasks: List[Task] = []
    result = await UserData.all()
    if not result:
        return
    loop = asyncio.get_event_loop()
    for n, data in enumerate(result):
        task = loop.create_task(update_user_info(data.osu_id))
        tasks.append(task)
        if n == 0:
            await asyncio.sleep(10)
        else:
            await asyncio.sleep(1)
    await asyncio.sleep(10)

    for _ in tasks:
        _.cancel()
    logger.info(f'已更新{len(result)}位玩家数据')


def mods2list(args: str) -> list:
    if '，' in args:
        sep = '，'
    elif ',' in args:
        sep = ','
    else:
        sep = ' '
    args = args.upper()
    return args.split(sep)
