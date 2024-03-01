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
    except NetworkError:
        return None


async def get_first_response(urls: List[str]):
    async with AsyncClient(timeout=100, proxies=proxy, follow_redirects=True) as client:
        tasks = [fetch_url(client, url) for url in urls]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            response = task.result()
            if response is not None:
                return response
        return None
