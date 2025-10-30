import base64
import hashlib
import re
import urllib
import random
import asyncio
import uuid
from pathlib import Path
from typing import Union, Optional
from io import BytesIO, TextIOWrapper

from nonebot.adapters.onebot.v11 import Bot
from nonebot.log import logger

from .schema import Badge
from .network import auto_retry
from .api import bg_url, safe_async_get
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
semaphore = asyncio.Semaphore(5)

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


@auto_retry
async def download_osu(set_id, map_id):
    url = [
        f"https://osu.ppy.sh/osu/{map_id}",
        f"https://osu.direct/api/osu/{map_id}",
        f"https://catboy.best/osu/{map_id}",
    ]
    logger.info(f"开始下载谱面: <{map_id}>")
    async with semaphore:
        if req := await get_first_response(url):
            filename = f"{map_id}.osu"
            filepath = map_path / str(set_id) / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(req.content)
            return filepath
        else:
            raise Exception("下载出错，请稍后再试")


async def get_projectimg(url: str) -> BytesIO:
    if "avatar-guest.png" in url:
        url = "https://osu.ppy.sh/images/layout/avatar-guest.png"
    req = await safe_async_get(url)
    if not req or req.status_code >= 400:
        # todo 加个自创的错误图片
        req = await safe_async_get(random.choice(bg_url))
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
    async with asyncio.Semaphore(5):
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
    path = badge_cache_path / f"{hash(badge.description)}.png"
    badge_icon = await get_projectimg(badge.image_url)
    with open(path, "wb") as f:
        f.write(badge_icon.getvalue())


# 保存个人信息界面背景
async def save_info_pic(user: str, byt: bytes):
    path = user_cache_path / user
    path.mkdir(parents=True, exist_ok=True)
    with open(path / "info.png", "wb") as f:
        f.write(BytesIO(byt).getvalue())


def calculate_file_chunks(file_path: str, chunk_size: int = 1024 * 64) -> tuple[list[bytes], str, int]:
    """
    计算文件分片和 SHA256

    Args:
        file_path: 文件路径
        chunk_size: 分片大小（默认64KB）

    Returns:
        (chunks, sha256_hash, total_size)
    """
    chunks = []
    hasher = hashlib.sha256()
    total_size = 0

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            hasher.update(chunk)
            total_size += len(chunk)

    sha256_hash = hasher.hexdigest()

    return chunks, sha256_hash, total_size


MAX_CONCURRENT_UPLOADS = 20


async def _upload_chunk(
    bot: "Bot",
    stream_id: str,
    chunk_data: bytes,
    chunk_index: int,
    total_chunks: int,
    total_size: int,
    sha256_hash: str,
    filename: str,
    semaphore: asyncio.Semaphore,
) -> None:
    """内部函数，用于异步上传单个文件分片"""
    async with semaphore:
        # 将分片数据编码为 base64
        chunk_base64 = base64.b64encode(chunk_data).decode("utf-8")

        # 构建参数
        params = {
            "stream_id": stream_id,
            "chunk_data": chunk_base64,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "file_size": total_size,
            "expected_sha256": sha256_hash,
            "filename": filename,
            "file_retention": 30 * 1000,
        }

        # 发送分片
        response = await bot.call_api("upload_file_stream", **params)

        logger.info(
            f"分片 {chunk_index + 1}/{total_chunks} 上传成功 "
            f"(接收: {response.get('received_chunks', 0)}/{response.get('total_chunks', 0)})"
        )


async def upload_file_stream_batch(bot: Bot, file_path: Path, chunk_size: int = 1024 * 64) -> str:
    """
    一次性批量上传文件流

    Args:
        bot: Bot 实例
        file_path: 要上传的文件路径
        chunk_size: 分片大小

    Returns:
        上传完成后的文件路径
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 分析文件
    chunks, sha256_hash, total_size = calculate_file_chunks(str(file_path), chunk_size)
    stream_id = str(uuid.uuid4())

    logger.info(f"\n开始上传文件: {file_path.name}")
    logger.info(f"流ID: {stream_id}")

    # 一次性发送所有分片
    total_chunks = len(chunks)
    # 创建信号量，限制最大并发数
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

    # 创建所有分片上传任务
    upload_tasks = []
    for chunk_index, chunk_data in enumerate(chunks):
        task = _upload_chunk(
            bot, stream_id, chunk_data, chunk_index, total_chunks, total_size, sha256_hash, file_path.name, semaphore
        )
        upload_tasks.append(task)

    try:
        await asyncio.gather(*upload_tasks)
    except Exception as e:
        logger.error(f"\n文件分片上传过程中发生错误: {e}")
        # 这里可以选择执行清理逻辑，如通知服务器取消上传
        raise e

    # 发送完成信号
    logger.info("\n所有分片发送完成，请求文件合并...")
    complete_params = {"stream_id": stream_id, "is_complete": True}

    response = await bot.call_api("upload_file_stream", **complete_params)

    if response.get("status") == "file_complete":
        logger.info("✅ 文件上传成功!")
        logger.info(f"  - 文件路径: {response.get('file_path')}")
        logger.info(f"  - 文件大小: {response.get('file_size')} 字节")
        logger.info(f"  - SHA256: {response.get('sha256')}")
        return response.get("file_path")
    else:
        raise Exception(f"文件状态异常: {response}")
