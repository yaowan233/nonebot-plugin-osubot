from pathlib import Path

from nonebot.exception import ParserExit, ActionFailed
from nonebot.internal.adapter import Message
from nonebot.params import ShellCommandArgv, CommandArg
from nonebot.rule import ArgumentParser
from nonebot import on_command, on_shell_command
from nonebot_plugin_alconna import UniMessage
from ..api import get_sayo_map_info

from ..mania import convert_mania_map, Options

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
async def _(argv: list[str] = ShellCommandArgv()):
    try:
        args = parser.parse_args(argv)
    except ParserExit as e:
        if e.status == 0:
            await UniMessage.image(path=Path(__file__).parent / 'osufile' / 'convert.jpg').finish(reply_to=True)
        await UniMessage.text(str(e)).finish(reply_to=True)
        return
    options = Options(**vars(args))
    if options.map:
        sayo_map_info = await get_sayo_map_info(options.map, 1)
        options.set = sayo_map_info.data.sid
        options.sayo_info = sayo_map_info
    if not options.set:
        await UniMessage.text('请提供需要转换的谱面setid').finish(reply_to=True)
    if options.nln and options.fln:
        await UniMessage.text('指令矛盾！').finish(reply_to=True)
    osz_file = await convert_mania_map(options)
    if not osz_file:
        await UniMessage.text('未找到该地图，请检查是否搞混了mapID与setID').finish(reply_to=True)
    file_path = osz_file.absolute()
    try:
        with open(file_path, 'rb') as f:
            await UniMessage.file(raw=f.read()).send()
    except ActionFailed:
        await UniMessage.text('上传文件失败，可能是群空间满或没有权限导致的').send(reply_to=True)
    finally:
        try:
            osz_file.unlink()
        except PermissionError:
            ...


change = on_command('倍速', priority=11, block=True)


@change.handle()
async def _(msg: Message = CommandArg()):
    args = msg.extract_plain_text().strip().split()
    argv = ['--map']
    if not args:
        await UniMessage.text('请输入需要倍速的地图mapID').finish(reply_to=True)
    set_id = args[0]
    if not set_id.isdigit():
        await UniMessage.text('请输入正确的mapID').finish(reply_to=True)
    argv.append(set_id)
    if len(args) >= 2:
        argv.append('--rate')
        if '-' in args[1]:
            low, high = args[1].split('-')
            argv.extend([low, '--end_rate', high, '--step', '0.05'])
        else:
            argv.append(args[1])
    else:
        await UniMessage.text('请输入倍速速率').finish(reply_to=True)
    args = parser.parse_args(argv)
    options = Options(**vars(args))
    if options.map:
        sayo_map_info = await get_sayo_map_info(options.map, 1)
        options.set = sayo_map_info.data.sid
        options.sayo_info = sayo_map_info
    osz_path = await convert_mania_map(options)
    if not osz_path:
        await UniMessage.text('未找到该地图，请检查是否搞混了mapID与setID').finish(reply_to=True)
    file_path = osz_path.absolute()
    try:
        with open(file_path, 'rb') as f:
            await UniMessage.file(raw=f.read()).send()
    except ActionFailed:
        await UniMessage.text('上传文件失败，可能是群空间满或没有权限导致的').send(reply_to=True)
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...


generate_full_ln = on_command('反键', priority=11, block=True)


@generate_full_ln.handle()
async def _(msg: Message = CommandArg()):
    args = msg.extract_plain_text().strip().split()
    if not args:
        await UniMessage.text('请输入需要转ln的地图setID').finish(reply_to=True)
    set_id = args[0]
    if not set_id.isdigit():
        await UniMessage.text('请输入正确的setID').finish(reply_to=True)
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
        await UniMessage.text('未找到该地图，请检查是否搞混了mapID与setID').finish(reply_to=True)
    file_path = osz_path.absolute()
    try:
        with open(file_path, 'rb') as f:
            await UniMessage.file(raw=f.read()).send()
    except ActionFailed:
        await UniMessage.text('上传文件失败，可能是群空间满或没有权限导致的').send(reply_to=True)
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...
