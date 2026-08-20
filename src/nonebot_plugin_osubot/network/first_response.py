from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit

import httpx
from nonebot.log import logger

from .manager import network_manager


@dataclass
class _MirrorHealth:
    reliability: float = 0.5
    latency: float | None = None

    def record(self, *, success: bool, latency: float) -> None:
        # Exponential moving averages favour recent observations without
        # permanently penalising a mirror for one temporary outage.
        weight = 0.2
        self.reliability = self.reliability * (1 - weight) + float(success) * weight
        self.latency = latency if self.latency is None else self.latency * (1 - weight) + latency * weight


@dataclass(frozen=True)
class _FetchResult:
    url: str
    response: httpx.Response | None
    latency: float


class MirrorRacer:
    """Return the first healthy mirror response and own all task cleanup."""

    def __init__(
        self,
        client_provider: Callable[[], Awaitable[httpx.AsyncClient]],
        *,
        hedge_delay: float = 0.15,
        clock: Callable[[], float] = monotonic,
    ):
        self._client_provider = client_provider
        self._hedge_delay = max(0.0, hedge_delay)
        self._clock = clock
        self._health: dict[str, _MirrorHealth] = {}

    async def request(self, urls: Sequence[str], *, timeout: float = 10.0) -> httpx.Response | None:
        ordered_urls = self._ordered_urls(urls)
        if not ordered_urls:
            return None

        client = await self._client_provider()
        remaining = iter(ordered_urls)
        tasks: set[asyncio.Task[_FetchResult]] = set()
        all_tasks: list[asyncio.Task[_FetchResult]] = []

        def start_next() -> bool:
            try:
                url = next(remaining)
            except StopIteration:
                return False
            task = asyncio.create_task(
                self._fetch(client, url, timeout),
                name=f"osubot-mirror-{urlsplit(url).netloc}",
            )
            tasks.add(task)
            all_tasks.append(task)
            return True

        start_next()
        try:
            while tasks:
                done, pending = await asyncio.wait(
                    tasks,
                    timeout=self._hedge_delay if len(all_tasks) < len(ordered_urls) else None,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                tasks = set(pending)

                if not done:
                    start_next()
                    continue

                for task in done:
                    result = task.result()
                    success = result.response is not None and result.response.status_code == 200
                    self._record(result.url, success=success, latency=result.latency)
                    if success:
                        return result.response

                # Do not wait for the hedge delay when every active mirror has
                # already failed; start the next fallback immediately.
                if not tasks:
                    start_next()
            return None
        finally:
            for task in all_tasks:
                if not task.done():
                    task.cancel()
            if all_tasks:
                await asyncio.gather(*all_tasks, return_exceptions=True)

    async def _fetch(self, client: httpx.AsyncClient, url: str, timeout: float) -> _FetchResult:
        started_at = self._clock()
        try:
            response = await client.get(url, timeout=timeout)
        except asyncio.CancelledError:
            raise
        except httpx.HTTPError as error:
            logger.debug(f"镜像请求失败: {url} ({error})")
            response = None
        return _FetchResult(url=url, response=response, latency=max(0.0, self._clock() - started_at))

    def _ordered_urls(self, urls: Sequence[str]) -> list[str]:
        indexed_urls = list(enumerate(dict.fromkeys(urls)))
        indexed_urls.sort(key=lambda item: (*self._rank(item[1]), item[0]))
        return [url for _, url in indexed_urls]

    def _rank(self, url: str) -> tuple[float, float]:
        health = self._health.get(self._origin(url))
        if health is None:
            return (-0.5, float("inf"))
        return (-health.reliability, health.latency if health.latency is not None else float("inf"))

    def _record(self, url: str, *, success: bool, latency: float) -> None:
        self._health.setdefault(self._origin(url), _MirrorHealth()).record(success=success, latency=latency)

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlsplit(url)
        return f"{parsed.scheme}://{parsed.netloc}".casefold()


mirror_racer = MirrorRacer(network_manager.get_client)


async def get_first_response(urls: list[str], timeout: float = 10.0) -> httpx.Response | None:
    return await mirror_racer.request(urls, timeout=timeout)
