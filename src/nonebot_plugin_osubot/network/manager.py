import httpx
import asyncio
from ..config import Config
from httpx import AsyncClient
from nonebot import get_plugin_config


plugin_config = get_plugin_config(Config)
proxy = plugin_config.osu_proxy


class NetworkManager:
    def __init__(self):
        self._client = None
        self._lock = asyncio.Lock()

    async def get_client(self) -> AsyncClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = AsyncClient(
                        proxy=proxy,
                        follow_redirects=True,
                        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100, keepalive_expiry=30),
                        timeout=httpx.Timeout(30.0),
                    )
        return self._client


network_manager = NetworkManager()
