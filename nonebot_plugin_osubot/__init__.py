import asyncio
import os
from asyncio.tasks import Task
from typing import List
from pathlib import Path

from nonebot.adapters.onebot.v11 import Event, Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment
from nonebot.internal.params import Depends
from nonebot.params import T_State
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.log import logger
from nonebot import on_command, require
from nonebot_plugin_tortoise_orm import add_model
from .draw import draw_info, draw_score, best_pfm, map_info, bmap_info, bindinfo, get_map_bg
from .file import download_map
from .utils import GM, GMN, update_user_info
from .database.models import UserData


require('nonebot_plugin_apscheduler')

from nonebot_plugin_apscheduler import scheduler


__plugin_meta__ = PluginMetadata(
    name="OSUBot",
    description="OSU查分插件",
    usage="使用/osuhelp查看使用帮助",
    extra={
        "unique_name": "osubot",
        "author": "yaowan233 <572473053@qq.com>",
        "version": "0.7.2",
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
            state['error'] = '该账号尚未绑定，请输入 bind 用户名 绑定账号'
            return
        user = user_data.osu_id
        mode = str(user_data.osu_mode)
        mods = []
        isint = True
        arg = msg.extract_plain_text().strip()
        mode_index = max(arg.find(':'), arg.find('：'))
        mods_index = arg.find('+')
        # 没有:与+时
        if max(mode_index, mods_index) < 0:
            para = arg
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
        if not para.isdigit():
            isint = False
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
        state['isint'] = isint
    return Depends(dependency)


info = on_command("info", block=True, priority=11)


@info.handle(parameterless=[split_msg()])
async def _info(state: T_State):
    if 'error' in state:
        await info.finish(state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    data = await draw_info(user, GM[mode])
    await info.finish(data, at_sender=True)


recent = on_command("recent", aliases={'re'}, priority=11, block=True)


@recent.handle(parameterless=[split_msg()])
async def _recent(state: T_State):
    if 'error' in state:
        await info.finish(state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    data = await draw_score('recent', user, GM[mode], [])
    await recent.finish(data, at_sender=True)

pr = on_command("pr", priority=11, block=True)


@pr.handle(parameterless=[split_msg()])
async def _pr(state: T_State):
    if 'error' in state:
        await info.finish(state['error'])
    user = state['para'] if state['para'] else state['user']
    mode = state['mode']
    data = await draw_score('pr', user, GM[mode], [])
    await recent.finish(data, at_sender=True)

score = on_command('score', priority=11, block=True)


@score.handle(parameterless=[split_msg()])
async def _score(state: T_State):
    if 'error' in state:
        await info.finish(state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    map_id = state['para']
    data = await draw_score('score', user, GM[mode], mapid=map_id, mods=mods)
    await score.finish(data, at_sender=True)


bp = on_command('bp', priority=11, block=True)


@bp.handle(parameterless=[split_msg()])
async def _bp(state: T_State):
    if 'error' in state:
        await info.finish(state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    best = state['para']
    if not best.isdigit():
        await bp.finish('只能接受纯数字的bp参数')
    best = int(best)
    if best <= 0 or best > 100:
        await bp.finish('只允许查询bp 1-100 的成绩', at_sender=True)
    data = await draw_score('bp', user, GM[mode], best=best, mods=mods)
    await bp.finish(data, at_sender=True)


pfm = on_command('pfm', priority=11, block=True)


@pfm.handle(parameterless=[split_msg()])
async def _pfm(state: T_State):
    if 'error' in state:
        await info.finish(state['error'])
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    para = state['para']
    try:
        low, high = limits(para)
    except Exception as e:
        await pfm.finish(f'{e}\n参数为 "数字-数字"的形式!')
        return
    if not 0 < low < high <= 100:
        await pfm.finish('仅支持查询bp1-100')
    data = await best_pfm('bp', user, GM[mode], mods, low, high)
    await pfm.finish(data, at_sender=True)


tbp = on_command('tbp', aliases={'todaybp'}, priority=11, block=True)


@tbp.handle(parameterless=[split_msg()])
async def _tbp(state: T_State):
    if 'error' in state:
        await info.finish(state['error'])
    user = state['user']
    mode = state['mode']
    data = await best_pfm('tbp', user, GM[mode], [])
    await tbp.finish(data, at_sender=True)


osu_map = on_command('map', priority=11, block=True)


@osu_map.handle()
async def _map(msg: Message = CommandArg()):
    mapid: list = msg.extract_plain_text().strip().split()
    mods = []
    while '' in mapid:
        mapid.remove('')
    if not mapid:
        await osu_map.finish('请输入地图ID', at_sender=True)
    elif not mapid[0].isdigit():
        await osu_map.finish('请输入正确的地图ID', at_sender=True)
    if '+' in mapid[-1]:
        mods = mods2list(mapid[-1][1:])
        del mapid[-1]
    m = await map_info(mapid[0], mods)
    await osu_map.finish(m, at_sender=True)


bmap = on_command('bmap', priority=11, block=True)


@bmap.handle()
async def _bmap(msg: Message = CommandArg()):
    msg: List[str] = msg.extract_plain_text().strip().split()
    while '' in msg:
        msg.remove('')
    if not msg:
        await bmap.finish('请输入地图ID', at_sender=True)
    op = False
    if len(msg) == 1:
        if not msg[0].isdigit():
            await bmap.finish('请输入正确的地图ID', at_sender=True)
        setid = msg[0]
    elif msg[0] == '-b':
        if not msg[1].isdigit():
            await bmap.finish('请输入正确的地图ID', at_sender=True)
        op = True
        setid = msg[1]
    else:
        await bmap.finish('请输入正确的地图ID', at_sender=True)
        return
    m = await bmap_info(setid, op)
    await bmap.finish(m, at_sender=True)


osudl = on_command('osudl', priority=11, block=True)


@osudl.handle()
async def _osudl(bot: Bot, ev: GroupMessageEvent, msg: Message = CommandArg()):
    gid = ev.group_id
    setid = msg.extract_plain_text().strip()
    if not setid:
        return
    if not setid.isdigit():
        await osudl.finish('请输入正确的地图ID', at_sender=True)
    filepath = await download_map(setid)
    await bot.upload_group_file(group_id=gid, file=str(filepath.absolute()), name=filepath.name)
    os.remove(filepath)


bind = on_command('bind', priority=11, block=True)


@bind.handle()
async def _bind(ev: Event, msg: Message = CommandArg()):
    qqid = ev.get_user_id()
    name = msg.extract_plain_text()
    if not name:
        await bind.finish('请输入您的 osuid', at_sender=True)
    if _ := await UserData.get_or_none(user_id=qqid):
        await bind.finish('您已绑定，如需要解绑请输入unbind', at_sender=True)
    msg = await bindinfo('bind', name, qqid)
    await bind.finish(msg, at_sender=True)


unbind = on_command('unbind', priority=11, block=True)


@unbind.handle()
async def _unbind(ev: Event):
    qqid = ev.get_user_id()
    if _ := await UserData.get_or_none(user_id=qqid):
        await UserData.filter(user_id=qqid).delete()
        await unbind.send('解绑成功！', at_sender=True)
    else:
        await unbind.finish('尚未绑定，无需解绑', at_sender=True)


update = on_command('update', priority=11, block=True)


@update.handle()
async def _recent(ev: Event, msg: Message = CommandArg()):
    qqid = ev.get_user_id()
    args: List[str] = msg.extract_plain_text().strip().split()
    while '' in args:
        args.remove('')
    user = await UserData.get_or_none(user_id=qqid)
    if not user:
        msg = '该账号尚未绑定，请输入 bind 用户名 绑定账号'
    elif not args:
        msg = '请输入需要更新内容的参数'
    elif args[0] == 'mode':
        try:
            mode = int(args[1])
        except Exception as e:
            logger.error(e)
            await update.finish('请输入正确的模式 0-3', at_sender=True)
            return
        if mode >= 0 or mode < 4:
            await UserData.filter(user_id=qqid).update(osu_mode=mode)
            msg = f'已将默认模式更改为 {GMN[mode]}'
        else:
            msg = '请输入正确的模式 0-3'
    else:
        msg = '参数错误，请输入正确的模式 0-3'
    await update.finish(msg, at_sender=True)


getbg = on_command('getbg', priority=11, block=True)


@getbg.handle()
async def _get_bg(msg: Message = CommandArg()):
    bg_id = msg.extract_plain_text().strip()
    if not bg_id:
        msg = '请输入需要提取BG的地图ID'
    else:
        msg = await get_map_bg(bg_id)
    await getbg.finish(msg, at_sender=True)


osu_help = on_command('osuhelp', priority=11, block=True)


@osu_help.handle()
async def _help():
    await osu_help.finish(MessageSegment.image(Path(__file__).parent / 'osufile' / 'help.png'), at_sender=True)


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


def limits(args: str) -> tuple:
    limit = args.split('-')
    low, high = int(limit[0]), int(limit[1])
    return low, high


def mods2list(args: str) -> list:
    if '，' in args:
        sep = '，'
    elif ',' in args:
        sep = ','
    else:
        sep = ' '
    args = args.upper()
    return args.split(sep)
