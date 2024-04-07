import asyncio
from typing import List

from httpx import NetworkError, AsyncClient
from nonebot import get_plugin_config
from ..config import Config

plugin_config = get_plugin_config(Config)
proxy = plugin_config.osu_proxy


async def fetch_url(client: AsyncClient, url):
    try:
        response = await client.get(url)
        if response.status_code == 200:
            return response.content
        else:
            return None
    except Exception:
        return None


async def get_first_response(urls: List[str]):
    async with AsyncClient(proxies=proxy, follow_redirects=True) as client:
        tasks = [fetch_url(client, url) for url in urls]
        try:
            for future in asyncio.as_completed(tasks, timeout=10):
                response = await future
                if response is not None:
                    return response
        except (asyncio.TimeoutError, Exception):
            pass
    return None
