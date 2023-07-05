from functools import wraps
from typing import TypeVar, Callable
from typing_extensions import ParamSpec
from nonebot import logger


T = TypeVar('T')
P = ParamSpec('P')


def auto_retry(func: Callable[P, T]) -> Callable[P, T]:
    @wraps(func)
    async def wrapper(*args, **kwargs):
        for i in range(10):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Retrying... {i + 1}/10")
                logger.exception(e)
        logger.error(f"多次重试失败，请检查网络连接")
    return wrapper
