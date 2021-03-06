from typing import Union
import aiohttp
import traceback
from nonebot.log import logger
from nonebot import get_driver
from expiringdict import ExpiringDict
from .config import Config

api = 'https://osu.ppy.sh/api/v2'
sayoapi = 'https://api.sayobot.cn'
ppcalcapi = 'http://106.53.138.218:6321/api/osu'
cache = ExpiringDict(max_len=1, max_age_seconds=86400)
plugin_config = Config.parse_obj(get_driver().config.dict())


if plugin_config.osu_key and plugin_config.osu_client:
    key = plugin_config.osu_key
    client_id = plugin_config.osu_client
else:
    raise Exception("请设置osu_key和osu_client")


async def renew_token():
    url = "https://osu.ppy.sh/oauth/token"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={'client_id': f'{client_id}', 'client_secret': f'{key}',
                                           'grant_type': 'client_credentials', 'scope': 'public'}) as req:
            if req.status == 200:
                osu_token = await req.json()
                cache.update({
                    'token': osu_token['access_token']
                })
            else:
                logger.error(f'更新OSU token出错 错误{req.status}')


async def osu_api(project: str, uid: Union[int, str] = 0, mode: str = 'osu', map_id: int = 0, isint: bool = False) -> \
        Union[str, dict]:
    try:
        if uid:
            if not isint:
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
    except Exception as e:
        logger.error(e)
        return {}


async def sayo_api(setid: int) -> dict:
    try:
        url = f'{sayoapi}/v2/beatmapinfo?0={setid}'
        return await api_info('mapinfo', url)
    except Exception as e:
        logger.error(e)
        return {}


async def pp_api(mode: int, map_id: int, acc: float = 0, combo: int = 0, perfect: int = 0, good: int = 0, bad: int = 0,
                 miss: int = 0, score: int = 1000000, mods=None) -> Union[dict, str]:
    if mods is None:
        mods = []
    try:
        if mode == 0:
            data = {
                'mode': mode,
                'map': map_id,
                'accuracy': acc,
                'combo': combo,
                'perfect': perfect,
                'good': good,
                'bad': bad,
                'miss': miss,
                'mods': mods
            }
        elif mode == 1:
            data = {
                'mode': mode,
                'map': map_id,
                'accuracy': acc,
                'combo': combo,
                'good': good,
                'miss': miss,
                'mods': mods
            }
        elif mode == 2:
            data = {
                'mode': mode,
                'map': map_id,
                'accuracy': acc,
                'combo': combo,
                'miss': miss,
                'mods': mods
            }
        elif mode == 3:
            data = {
                'mode': mode,
                'map': map_id,
                'score': score,
                'mods': mods
            }
        else:
            raise 'mode Error'
        async with aiohttp.ClientSession() as session:
            async with session.post(ppcalcapi, json=data) as req:
                return await req.json()
    except Exception as e:
        logger.error(traceback.print_exc())
        return f'Error: {type(e)}'


async def get_user_info(url: str) -> Union[dict, str]:
    try:
        token = cache.get('token')
        if not token:
            await renew_token()
            token = cache.get('token')
        header = {'Authorization': f'Bearer {token}'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=header) as req:
                if req.status == 401:
                    await token.update_token()
                    return await get_user_info(url)
                elif req.status == 404:
                    return '未找到该玩家，请确认玩家ID'
                elif req.status == 200:
                    return await req.json()
                else:
                    return 'API请求失败，请联系管理员'
    except Exception as e:
        logger.error(traceback.print_exc())
        return f'Error: {type(e)}'


async def api_info(project: str, url: str) -> Union[dict, str]:
    try:
        if project == 'mapinfo' or project == 'PPCalc':
            headers = {
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/78.0.3904.108'}
        else:
            token = cache.get('token')
            if not token:
                await renew_token()
                token = cache.get('token')
            headers = {'Authorization': f'Bearer {token}'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as req:
                if req.status == 404:
                    if project == 'info' or project == 'bind':
                        return '未找到该玩家，请确认玩家ID'
                    elif project == 'recent':
                        return '未找到该玩家，请确认玩家ID'
                    elif project == 'score':
                        return '未找到该地图成绩，请确认地图ID或模式'
                    elif project == 'bp':
                        return '未找到该玩家BP'
                    elif project == 'map':
                        return '未找到该地图，请确认地图ID'
                    else:
                        return 'API请求失败，请联系管理员或稍后再尝试'
                if project == 'mapinfo':
                    return await req.json(content_type='text/html', encoding='utf-8')
                else:
                    return await req.json()
    except Exception as e:
        logger.error(traceback.print_exc())
        return f'Error: {type(e)}'
