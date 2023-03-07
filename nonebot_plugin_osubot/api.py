from httpx import AsyncClient
from typing import Union
from nonebot.log import logger
from nonebot import get_driver
from expiringdict import ExpiringDict
from .config import Config
from .network import auto_retry

api = 'https://osu.ppy.sh/api/v2'
sayoapi = 'https://api.sayobot.cn'
pp_calc_api = 'https://api.yuzuai.xyz/osu/ppcalc'
cache = ExpiringDict(max_len=1, max_age_seconds=86400)
plugin_config = Config.parse_obj(get_driver().config.dict())

if plugin_config.osu_key and plugin_config.osu_client:
    key = plugin_config.osu_key
    client_id = plugin_config.osu_client
else:
    raise Exception("请设置osu_key和osu_client")


async def renew_token():
    url = "https://osu.ppy.sh/oauth/token"
    async with AsyncClient() as client:
        client: AsyncClient
        req = await client.post(url, json={'client_id': f'{client_id}', 'client_secret': f'{key}',
                                           'grant_type': 'client_credentials', 'scope': 'public'})
    if req.status_code == 200:
        osu_token = req.json()
        cache.update({
            'token': osu_token['access_token']
        })
    else:
        logger.error(f'更新OSU token出错 错误{req.status_code}')


async def osu_api(project: str, uid: int = 0, mode: str = 'osu', map_id: int = 0) -> Union[str, dict]:
    if uid:
        info = await get_user_info(f'{api}/users/{uid}')
        if isinstance(info, str):
            return info
        else:
            uid = info['id']
    if project == 'info' or project == 'bind' or project == 'update':
        url = f'{api}/users/{uid}/{mode}'
    elif project == 'recent':
        url = f'{api}/users/{uid}/scores/{project}?mode={mode}&include_fails=1'
    elif project == 'pr':
        url = f'{api}/users/{uid}/scores/recent?mode={mode}'
    elif project == 'score':
        if mode != 'osu':
            url = f'{api}/beatmaps/{map_id}/scores/users/{uid}?mode={mode}'
        else:
            url = f'{api}/beatmaps/{map_id}/scores/users/{uid}'
    elif project == 'bp':
        url = f'{api}/users/{uid}/scores/best?mode={mode}&limit=100'
    elif project == 'map':
        url = f'{api}/beatmaps/{map_id}'
    else:
        raise 'Project Error'
    return await api_info(project, url)


async def sayo_api(setid: int) -> dict:
    url = f'{sayoapi}/v2/beatmapinfo?0={setid}'
    return await api_info('mapinfo', url)


@auto_retry
async def get_user_info(url: str) -> Union[dict, str]:
    token = cache.get('token')
    if not token:
        await renew_token()
        token = cache.get('token')
    header = {'Authorization': f'Bearer {token}'}
    async with AsyncClient() as client:
        client: AsyncClient
        req = await client.get(url, headers=header)
    if req.status_code == 401:
        await token.update_token()
        return await get_user_info(url)
    elif req.status_code == 404:
        return '未找到该玩家，请确认玩家ID是否正确，有无多余或缺少的空格'
    elif req.status_code == 200:
        return req.json()
    else:
        return 'API请求失败，请联系管理员'


@auto_retry
async def api_info(project: str, url: str) -> Union[dict, str]:
    if project == 'mapinfo' or project == 'PPCalc':
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/78.0.3904.108'}
    else:
        token = cache.get('token')
        if not token:
            await renew_token()
            token = cache.get('token')
        headers = {'Authorization': f'Bearer {token}'}
    async with AsyncClient(timeout=100) as client:
        client: AsyncClient
        req = await client.get(url, headers=headers)
    if req.status_code == 404:
        if project == 'info' or project == 'bind':
            return '未找到该玩家，请确认玩家ID'
        elif project == 'recent':
            return '未找到该玩家，请确认玩家ID'
        elif project == 'score':
            return '未找到该地图成绩，请检查是否搞混了mapID与setID或模式'
        elif project == 'bp':
            return '未找到该玩家BP'
        elif project == 'map':
            return '未找到该地图，请检查是否搞混了mapID与setID'
        else:
            return 'API请求失败，请联系管理员或稍后再尝试'
    return req.json()


@auto_retry
async def get_random_bg() -> bytes:
    async with AsyncClient() as client:
        client: AsyncClient
    res = await client.get('https://api.gmit.vip/Api/DmImg?format=image', follow_redirects=True)
    return res.content
