from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from time import monotonic

import httpx
from nonebot.log import logger


class RequestPriority(str, Enum):
    FOREGROUND = "foreground"
    BACKGROUND = "background"


class ApiQueueFull(RuntimeError):
    pass


_current_priority: ContextVar[RequestPriority] = ContextVar(
    "nonebot_plugin_osubot_api_priority",
    default=RequestPriority.FOREGROUND,
)


@contextmanager
def osu_api_priority(priority: RequestPriority) -> Iterator[None]:
    """Apply one priority to all osu! API calls in the current async context."""
    token = _current_priority.set(priority)
    try:
        yield
    finally:
        _current_priority.reset(token)


@dataclass(frozen=True)
class SchedulerSnapshot:
    foreground_queued: int
    background_queued: int
    in_flight: int
    completed: int
    failed: int
    retried: int
    rate_limited: int


@dataclass
class _QueuedRequest:
    operation: Callable[[], Awaitable[httpx.Response]]
    future: asyncio.Future[httpx.Response]
    priority: RequestPriority


class _RateGate:
    def __init__(
        self,
        rate: float,
        *,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
    ):
        self._interval = 1.0 / max(rate, 0.001)
        self._clock = clock
        self._sleep = sleep
        self._next_at = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = self._clock()
            scheduled_at = max(now, self._next_at)
            self._next_at = scheduled_at + self._interval
        delay = scheduled_at - now
        if delay > 0:
            await self._sleep(delay)

    async def defer(self, delay: float) -> None:
        async with self._lock:
            self._next_at = max(self._next_at, self._clock() + max(0.0, delay))


class OsuApiScheduler:
    """Prioritize interactive osu! API traffic and bound background work.

    Callers submit one HTTP operation. Queueing, lane isolation, rate pacing,
    retry policy, and lifecycle stay behind this interface.
    """

    def __init__(
        self,
        *,
        max_concurrency: int = 8,
        foreground_rate: float = 8.0,
        background_rate: float = 1.0,
        queue_size: int = 512,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
        queue_wait_timeout: float = 5.0,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        if max_concurrency < 2:
            raise ValueError("max_concurrency must reserve at least one worker per priority")
        self._foreground_queue: asyncio.Queue[_QueuedRequest] = asyncio.Queue(maxsize=max(1, queue_size))
        self._background_queue: asyncio.Queue[_QueuedRequest] = asyncio.Queue(maxsize=max(1, queue_size))
        self._foreground_workers = max_concurrency - 1
        self._background_workers = 1
        self._foreground_gate = _RateGate(foreground_rate, clock=clock, sleep=sleep)
        self._background_gate = _RateGate(background_rate, clock=clock, sleep=sleep)
        self._max_retries = max(0, max_retries)
        self._retry_base_delay = max(0.0, retry_base_delay)
        self._queue_wait_timeout = max(0.1, queue_wait_timeout)
        self._sleep = sleep
        self._workers: list[asyncio.Task[None]] = []
        self._start_lock = asyncio.Lock()
        self._in_flight = 0
        self._completed = 0
        self._failed = 0
        self._retried = 0
        self._rate_limited = 0

    async def request(
        self,
        operation: Callable[[], Awaitable[httpx.Response]],
        *,
        priority: RequestPriority | None = None,
    ) -> httpx.Response:
        await self._ensure_started()
        actual_priority = priority or _current_priority.get()
        loop = asyncio.get_running_loop()
        item = _QueuedRequest(operation, loop.create_future(), actual_priority)
        queue = self._queue(actual_priority)

        if actual_priority is RequestPriority.BACKGROUND:
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull as error:
                raise ApiQueueFull("osu! API background queue is full") from error
        else:
            try:
                await asyncio.wait_for(queue.put(item), timeout=self._queue_wait_timeout)
            except TimeoutError as error:
                raise ApiQueueFull("osu! API foreground queue is full") from error

        return await item.future

    def snapshot(self) -> SchedulerSnapshot:
        return SchedulerSnapshot(
            foreground_queued=self._foreground_queue.qsize(),
            background_queued=self._background_queue.qsize(),
            in_flight=self._in_flight,
            completed=self._completed,
            failed=self._failed,
            retried=self._retried,
            rate_limited=self._rate_limited,
        )

    async def close(self) -> None:
        workers, self._workers = self._workers, []
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._cancel_queued(self._foreground_queue)
        self._cancel_queued(self._background_queue)

    async def _ensure_started(self) -> None:
        if self._workers and all(not worker.done() for worker in self._workers):
            return
        async with self._start_lock:
            if self._workers and all(not worker.done() for worker in self._workers):
                return
            self._workers = [
                *(
                    asyncio.create_task(
                        self._worker(self._foreground_queue, self._foreground_gate),
                        name=f"osubot-osu-api-foreground-{index}",
                    )
                    for index in range(self._foreground_workers)
                ),
                *(
                    asyncio.create_task(
                        self._worker(self._background_queue, self._background_gate),
                        name=f"osubot-osu-api-background-{index}",
                    )
                    for index in range(self._background_workers)
                ),
            ]

    async def _worker(
        self,
        queue: asyncio.Queue[_QueuedRequest],
        gate: _RateGate,
    ) -> None:
        while True:
            item = await queue.get()
            try:
                if item.future.cancelled():
                    continue
                self._in_flight += 1
                try:
                    response = await self._execute(item.operation, gate)
                except asyncio.CancelledError:
                    item.future.cancel()
                    raise
                except Exception as error:
                    self._failed += 1
                    if not item.future.done():
                        item.future.set_exception(error)
                else:
                    self._completed += 1
                    if not item.future.done():
                        item.future.set_result(response)
                finally:
                    self._in_flight -= 1
            finally:
                queue.task_done()

    async def _execute(
        self,
        operation: Callable[[], Awaitable[httpx.Response]],
        gate: _RateGate,
    ) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            await gate.wait()
            try:
                response = await operation()
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt >= self._max_retries:
                    raise
                self._retried += 1
                await self._sleep(self._retry_base_delay * 2**attempt)
                continue

            retry_delay: float | None = None
            if response.status_code == 429:
                self._rate_limited += 1
                retry_delay = self._retry_after(response, attempt)
                await asyncio.gather(
                    self._foreground_gate.defer(retry_delay),
                    self._background_gate.defer(retry_delay),
                )
            elif 500 <= response.status_code < 600:
                retry_delay = self._retry_base_delay * 2**attempt

            if retry_delay is None or attempt >= self._max_retries:
                return response
            self._retried += 1
            if response.status_code != 429:
                await self._sleep(retry_delay)

        raise RuntimeError("unreachable osu! API retry state")

    def _retry_after(self, response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After", "").strip()
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                try:
                    target = parsedate_to_datetime(value)
                    if target.tzinfo is None:
                        target = target.replace(tzinfo=timezone.utc)
                    return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    logger.debug(f"无法解析 osu! API Retry-After: {value}")
        return self._retry_base_delay * 2**attempt

    def _queue(self, priority: RequestPriority) -> asyncio.Queue[_QueuedRequest]:
        if priority is RequestPriority.BACKGROUND:
            return self._background_queue
        return self._foreground_queue

    @staticmethod
    def _cancel_queued(queue: asyncio.Queue[_QueuedRequest]) -> None:
        while True:
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            item.future.cancel()
            queue.task_done()
