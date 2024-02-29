import urllib
from arclet.alconna import Alconna, Args, CommandMeta
from nonebot_plugin_alconna import on_alconna, UniMessage, Match
from ..file import download_map

osudl = on_alconna(
    Alconna(
        "osudl",
        Args["setid?", str],
        meta=CommandMeta(example="/getbg 4374648"),
    ),
    skip_for_unmatch=False,
    use_cmd_start=True,
)


@osudl.handle()
async def _osudl(
    setid: Match[str],
):
    setid = setid.result.strip() if setid.available else ""
    if not setid or not setid.isdigit():
        await UniMessage.text("请输入正确的地图ID").send(reply_to=True)
    osz_path = await download_map(int(setid))
    name = urllib.parse.unquote(osz_path.name)
    file_path = osz_path.absolute()
    try:
        await UniMessage.file(path=file_path).send()
    except Exception as e:
        await UniMessage.text("上传文件失败，可能是群空间满或没有权限导致的").send(reply_to=True)
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...
