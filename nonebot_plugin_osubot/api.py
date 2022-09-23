import json
from typing import Union, Optional
import aiohttp
from nonebot.log import logger
from nonebot import get_driver
from expiringdict import ExpiringDict
from .config import Config
from .schema import Score

api = 'https://osu.ppy.sh/api/v2'
sayoapi = 'https://api.sayobot.cn'
pp_calc_api = 'https://api.yuzuai.xyz/osu'
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


async def osu_api(project: str, uid: int = 0, mode: str = 'osu', map_id: int = 0) -> \
        Union[str, dict]:
    if uid and not str(uid).isdigit():
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


async def pp_api(mode: int, score: Optional[Score], data=None) -> dict:
    if data is None:
        data = {
            'BeatmapID': score.beatmap.id,
            'Mode': mode,
            'Accuracy': score.accuracy,
            'Combo': score.max_combo,
            'C300': score.statistics.count_300,
            'C100': score.statistics.count_100,
            'C50': score.statistics.count_50,
            'Geki': score.statistics.count_geki,
            'Katu': score.statistics.count_katu,
            'Miss': score.statistics.count_miss,
            'Mods': ''.join(score.mods),
            'Score': score.score,
            'isPlay': 'True'
        }
    async with aiohttp.ClientSession() as session:
        async with session.get(pp_calc_api, params=data) as req:
            text = await req.text()
            return json.loads(text)


async def get_user_info(url: str) -> Union[dict, str]:
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
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as req:
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
