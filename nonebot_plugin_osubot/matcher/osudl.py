import asyncio
import base64
import hashlib
import uuid
from pathlib import Path

from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.internal.adapter import Message
from nonebot_plugin_alconna import UniMessage

from ..file import download_map

osudl = on_command("osudl", priority=11, block=True)


def calculate_file_chunks(file_path: str, chunk_size: int = 1024 * 16) -> tuple[list[bytes], str, int]:
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


async def upload_file_stream_batch(bot: Bot, file_path: Path, chunk_size: int = 1024 * 16) -> str:
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


@osudl.handle()
async def _osudl(bot: Bot, event: GroupMessageEvent, setid: Message = CommandArg()):
    setid = setid.extract_plain_text().strip()
    if not setid or not setid.isdigit():
        await UniMessage.text("请输入正确的地图ID").send(reply_to=True)
    osz_path = await download_map(int(setid))
    server_osz_path = await upload_file_stream_batch(bot, osz_path)
    try:
        await bot.call_api("upload_group_file", group_id=event.group_id, file=server_osz_path, name=osz_path.name)
    except Exception:
        await UniMessage.text("上传文件失败，可能是群空间满或没有权限导致的").send(reply_to=True)
    finally:
        try:
            osz_path.unlink()
        except PermissionError:
            ...
