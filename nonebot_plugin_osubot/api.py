from io import BytesIO
from httpx import AsyncClient, Response
from typing import Union
from nonebot.log import logger
from nonebot import get_driver
from expiringdict import ExpiringDict
from .config import Config
from .network import auto_retry
from .schema import SayoBeatmap, RecommendData

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


@auto_retry
async def safe_async_get(url, headers=None) -> Response:
    async with AsyncClient(timeout=100) as client:
        client: AsyncClient
        req = await client.get(url, headers=headers, follow_redirects=True)
    return req


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


async def get_user_info(url: str) -> Union[dict, str]:
    token = cache.get('token')
    if not token:
        await renew_token()
        token = cache.get('token')
    header = {'Authorization': f'Bearer {token}'}
    req = await safe_async_get(url, headers=header)
    if req.status_code == 401:
        await token.update_token()
        return await get_user_info(url)
    elif req.status_code == 404:
        return '未找到该玩家，请确认玩家ID是否正确，有无多余或缺少的空格'
    elif req.status_code == 200:
        return req.json()
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
    req = await safe_async_get(url, headers=headers)
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


async def get_random_bg() -> bytes:
    res = await safe_async_get('https://api.gmit.vip/Api/DmImg?format=image')
    return res.content


async def get_sayo_map_info(sid, t=0) -> SayoBeatmap:
    res = await safe_async_get(f'https://api.sayobot.cn/v2/beatmapinfo?K={sid}&T={t}')
    return SayoBeatmap(**res.json())


async def get_map_bg(sid, bg_name):
    res = await safe_async_get(f'https://dl.sayobot.cn/beatmaps/files/{sid}/{bg_name}')
    return BytesIO(res.content)


async def get_recommend(uid, mode):
    headers = {'uid': str(uid)}
    params = {'newRecordPercent': '0,1',
              'passPercent': '0.4,1',
              'difficulty': '0,15',
              'keyCount': '4,7',
              'gameMode': mode,
              'rule': '4',
              'current': '1',
              'pageSize': '20'}
    res = await safe_async_get('https://alphaosu.keytoix.vip/api/v1/self/maps/recommend', headers=headers,
                               params=params)
    return RecommendData(**res.json())
