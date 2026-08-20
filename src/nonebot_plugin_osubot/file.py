import re
import hashlib
import urllib
import asyncio
from pathlib import Path
from typing import Union, Optional
from io import BytesIO, TextIOWrapper

from nonebot.log import logger

from .schema import Badge
from .exceptions import NetworkError
from .network import auto_retry
from .api import safe_async_get
from .network.first_response import get_first_response

osufile = Path(__file__).parent / "osufile"
map_path = Path() / "data" / "osu" / "map"
user_cache_path = Path() / "data" / "osu" / "user"
badge_cache_path = Path() / "data" / "osu" / "badge"
team_cache_path = Path() / "data" / "osu" / "team"
api_ls = [
    "https://osu.direct/api/d/",
    "https://txy1.sayobot.cn/beatmaps/download/novideo/",
    "https://catboy.best/d/",
]
osu_download_semaphore = asyncio.Semaphore(5)
image_download_semaphore = asyncio.Semaphore(5)

map_path.mkdir(parents=True, exist_ok=True)
user_cache_path.mkdir(parents=True, exist_ok=True)
badge_cache_path.mkdir(parents=True, exist_ok=True)
team_cache_path.mkdir(parents=True, exist_ok=True)


def extract_filename_from_headers(headers: dict[str, str]) -> Optional[str]:
    """
    从 Content-Disposition 响应头中提取文件名，并处理 URL 编码。

    Args:
        headers: 响应头字典。

    Returns:
        提取到的文件名字符串，如果失败则返回 None。
    """
    disposition = headers.get("content-disposition", "")
    if not disposition:
        return None

    match_utf8 = re.search(r"filename\*=(?:utf-8''|)(.+?)(?:;|$)", disposition, re.IGNORECASE)

    if match_utf8:
        # 提取匹配到的文件名部分
        encoded_filename = match_utf8.group(1).strip('"').strip()

        try:
            return urllib.parse.unquote(encoded_filename)
        except Exception as e:
            # 如果解码失败，记录错误并尝试使用原始编码
            print(f"警告: 解码 filename* 失败: {e}. 使用原始编码.")
            return encoded_filename

    match_normal = re.search(r"filename=\"?(.+?)\"?(\s|;|$)", disposition, re.IGNORECASE)
    if match_normal:
        # 普通 filename 字段也可能包含 URL 编码，进行解码
        filename = match_normal.group(1).strip('"').strip()
        try:
            return urllib.parse.unquote(filename)
        except Exception:
            return filename

    return None


async def download_map(setid: int) -> Optional[Path]:
    urls = [f"{base_url}{setid}" for base_url in api_ls]
    logger.info(f"开始下载地图: <{setid}>")
    req = await get_first_response(urls)
    filename = extract_filename_from_headers(req.headers)
    filepath = map_path.parent / filename
    with open(filepath.absolute(), "wb") as f:
        f.write(req.content)
    logger.info(f"地图: <{setid}> 下载完毕")
    return filepath.absolute()


def osu_file_matches_checksum(path: Path, checksum: str | None) -> bool:
    """Return whether a cached .osu file matches the API checksum."""
    if not path.exists():
        return False
    expected = (checksum or "").strip().casefold()
    if not expected:
        return True
    digest = hashlib.md5()  # noqa: S324 - osu! uses MD5 as a cache identity, not for security
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected


@auto_retry
async def download_osu(set_id, map_id, checksum: str | None = None):
    url = [
        f"https://osu.ppy.sh/osu/{map_id}",
        f"https://osu.direct/api/osu/{map_id}",
        f"https://catboy.best/osu/{map_id}",
    ]
    logger.info(f"开始下载谱面: <{map_id}>")
    async with osu_download_semaphore:
        if req := await get_first_response(url):
            filename = f"{map_id}.osu"
            filepath = map_path / str(set_id) / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            content = req.content
            expected = (checksum or "").strip().casefold()
            actual = hashlib.md5(content).hexdigest()  # noqa: S324
            if expected and actual != expected:
                official = await safe_async_get(url[0])
                if not official or official.status_code >= 400:
                    raise NetworkError("下载的谱面文件校验失败")
                content = official.content
                actual = hashlib.md5(content).hexdigest()  # noqa: S324
                if actual != expected:
                    raise NetworkError("下载的谱面文件与官网 checksum 不一致")
            task_id = id(asyncio.current_task())
            temporary = filepath.with_name(f".{filename}.{task_id}.tmp")
            try:
                with temporary.open("wb") as file:
                    file.write(content)
                temporary.replace(filepath)
            finally:
                temporary.unlink(missing_ok=True)
            return filepath
        else:
            raise Exception("下载出错，请稍后再试")


async def ensure_osu_file(set_id, map_id, checksum: str | None = None) -> Path:
    """Reuse a current cached .osu file, refreshing stale revisions by checksum."""
    filepath = map_path / str(set_id) / f"{map_id}.osu"
    if osu_file_matches_checksum(filepath, checksum):
        return filepath
    if filepath.exists() and checksum:
        logger.info(f"谱面缓存 checksum 已变化，重新下载: <{map_id}>")
    downloaded = await download_osu(set_id, map_id, checksum)
    if downloaded is None:
        raise NetworkError("谱面文件下载失败")
    return downloaded


async def get_projectimg(url: str) -> BytesIO:
    if "avatar-guest.png" in url:
        url = "https://osu.ppy.sh/images/layout/avatar-guest.png"
    async with image_download_semaphore:
        req = await safe_async_get(url)
    if not req or req.status_code >= 400:
        raise Exception("图片下载失败")
    data = req.read()
    im = BytesIO(data)
    return im


async def get_pfm_img(url: str, cache_path: Path) -> BytesIO:
    cache_dir = cache_path.parent
    cache_dir.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        with cache_path.open("rb") as f:
            return BytesIO(f.read())
    async with image_download_semaphore:
        req = await safe_async_get(url)
    if not req or req.status_code >= 400:
        return BytesIO()
    image_data = req.content
    with cache_path.open("wb") as f:
        f.write(image_data)
    return BytesIO(image_data)


def re_map(file: Union[bytes, Path]) -> str:
    if isinstance(file, bytes):
        text = TextIOWrapper(BytesIO(file), "utf-8").read()
    else:
        with open(file, encoding="utf-8") as f:
            text = f.read()
    res = re.search(r"\d,\d,\"(.+)\"", text)
    bg = "mapbg.png" if not res else res.group(1).strip()
    if "/" in bg:
        bg = bg.split("/")[-1]
    return bg


async def make_badge_cache_file(badge: Badge):
    path = badge_cache_file(badge)
    if path.exists():
        return path
    badge_icon = await asyncio.wait_for(get_projectimg(badge.image_url), timeout=3)
    task_id = id(asyncio.current_task())
    temporary = path.with_name(f".{path.name}.{task_id}.tmp")
    try:
        temporary.write_bytes(badge_icon.getvalue())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def badge_cache_file(badge: Badge) -> Path:
    """Return a stable badge cache path that survives Python process restarts."""
    identity = f"{badge.image_url}\0{badge.description}".encode()
    digest = hashlib.sha256(identity).hexdigest()[:24]
    return badge_cache_path / f"{digest}.png"
