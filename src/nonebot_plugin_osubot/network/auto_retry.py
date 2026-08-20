from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import wraps
from typing import ParamSpec, TypeVar

import httpx
from nonebot import logger


T = TypeVar("T")
P = ParamSpec("P")


class RetryPolicy:
    """Retry only failures that a later HTTP attempt can reasonably recover."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        jitter_ratio: float = 0.2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ):
        self._max_attempts = max(1, max_attempts)
        self._base_delay = max(0.0, base_delay)
        self._max_delay = max(0.0, max_delay)
        self._jitter_ratio = max(0.0, jitter_ratio)
        self._sleep = sleep
        self._jitter = jitter

    async def run(self, operation: Callable[[], Awaitable[T]], *, operation_name: str = "HTTP request") -> T:
        for attempt in range(1, self._max_attempts + 1):
            try:
                result = await operation()
            except asyncio.CancelledError:
                raise
            except (httpx.TimeoutException, httpx.TransportError) as error:
                if attempt >= self._max_attempts:
                    logger.error(f"{operation_name} 网络重试耗尽: {error}")
                    raise
                delay = self._backoff(attempt)
                logger.warning(
                    f"{operation_name} 网络请求失败，将在 {delay:.2f}s 后重试 ({attempt}/{self._max_attempts}): {error}"
                )
                await self._sleep(delay)
                continue

            if not isinstance(result, httpx.Response) or not self._retryable_status(result.status_code):
                return result
            if attempt >= self._max_attempts:
                logger.error(f"{operation_name} HTTP {result.status_code} 重试耗尽")
                return result

            delay = self._response_delay(result, attempt)
            logger.warning(
                f"{operation_name} 收到 HTTP {result.status_code}，将在 {delay:.2f}s 后重试 "
                f"({attempt}/{self._max_attempts})"
            )
            await self._sleep(delay)

        raise RuntimeError("unreachable retry state")

    @staticmethod
    def _retryable_status(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code < 600

    def _response_delay(self, response: httpx.Response, attempt: int) -> float:
        if response.status_code == 429:
            retry_after = self._parse_retry_after(response.headers.get("Retry-After", ""))
            if retry_after is not None:
                return retry_after
        return self._backoff(attempt)

    def _backoff(self, attempt: int) -> float:
        base = min(self._max_delay, self._base_delay * 2 ** max(0, attempt - 1))
        jitter = self._jitter(0.0, base * self._jitter_ratio) if base > 0 else 0.0
        return min(self._max_delay, base + max(0.0, jitter))

    @staticmethod
    def _parse_retry_after(value: str) -> float | None:
        value = value.strip()
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                target = parsedate_to_datetime(value)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None


retry_policy = RetryPolicy()


def auto_retry(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return await retry_policy.run(lambda: func(*args, **kwargs), operation_name=func.__qualname__)

    return wrapper
