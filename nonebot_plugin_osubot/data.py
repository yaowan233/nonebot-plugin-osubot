from datetime import datetime, timedelta
from time import mktime, strptime
from typing import List

from .mods import Mods


class UserInfo:
    """
    个人信息
    """

    def __init__(self, info: dict):
        """
        返回 `info` 数据
        """
        self.icon: str = info['avatar_url']
        self.country_code: str = info['country_code']
        self.uid: int = info['id']
        self.user_status: bool = info['is_online']
        self.supporter: bool = info['is_supporter']
        self.username: str = info['username']
        self.cover_url: str = info['cover_url']
        self.badges: list = info['badges']
        self.play: dict = info['statistics']
        self.level: dict = self.play['level']
        self.current: int = self.level['current']
        self.progress: int = self.level['progress']
        self.grank: int = self.play['global_rank'] if self.play['global_rank'] else 0
        self.pp: float = self.play['pp']
        self.r_score: int = self.play['ranked_score']
        self.acc: float = round(self.play['hit_accuracy'], 2)
        self.play_count: int = self.play['play_count']
        self.play_time: int = self.play['play_time']
        self.play_hits: int = self.play['total_hits']
        self.t_score: int = self.play['total_score']
        self.count: int = self.play['total_hits']
        self.g_counts: dict = self.play['grade_counts']
        self.gc: tuple = self.g_counts['ssh'], self.g_counts['ss'], self.g_counts['sh'], self.g_counts['s'], \
                         self.g_counts['a']
        self.crank: int = self.play['country_rank'] if self.play['country_rank'] else 0


class ScoreInfo:
    """
    成绩信息
    """

    info = None

    def __init__(self, info: dict):
        """
        返回 `score` 数据
        """
        self.bpList = []
        self.info = info

    def _get_all_score(self, info: dict):
        """
        返回 `score` 数据
        """
        self.uid: int = info['user_id']
        self.acc: float = info['accuracy']
        self.mods: list = info['mods']
        self.score: int = info['score']
        self.maxcb: int = info['max_combo']
        self.count: dict = info['statistics']
        self.mode: int = info['mode_int']
        self.c50: int = self.count['count_50']
        self.c100: int = self.count['count_100']
        self.c300: int = self.count['count_300']
        self.cgeki: int = self.count['count_geki']
        self.ckatu: int = self.count['count_katu']
        self.cmiss: int = self.count['count_miss']
        self.rank: int = info['rank']
        self.date: str = info['created_at']
        self.pp: float = info['pp'] if info['pp'] else -1
        self.setid: int = info['beatmap']['beatmapset_id']
        self.mapid: int = info['beatmap']['id']
        self.version: str = info['beatmap']['version']
        self.map_status: str = info['beatmap']['status']
        self.user: dict = info['user']
        self.icon_url: str = self.user['avatar_url']
        self.country_code: str = self.user['country_code']
        self.user_status: bool = self.user['is_online']
        self.supporter: bool = self.user['is_supporter']
        self.username: str = self.user['username']

    def _set_mods(self, mods: list, max: int = 0, best: bool = False):
        """
        计算开启 `mod` 的数字和
        """
        self.mods_list = Mods(self.info, mods).getmodslist()
        if len(self.mods_list) > max:
            self.mods_list = self.mods_list[:max]
        elif best:
            self.mods_list = False

    def recent_score(self):
        """
        返回 `recent` 数据
        """
        self._get_all_score(self.info[0])

    def bp_score(self, best: int, mods=None):
        """
        返回 `BP` 数据
        """
        if mods is None:
            mods = []
        if mods:
            self._set_mods(mods, best, True)
            if self.mods_list:
                self.info = self.info[self.mods_list[best - 1]]
            else:
                self.info = self.mods_list
                return
        else:
            self.info = self.info[best - 1]

        self._get_all_score(self.info)

    def map_score(self, mods=None):
        """
        返回 `Score` 成绩数据
        """
        self.grank: int = self.info['position']
        self.info: List[dict] = [self.info['score']]
        self.headericon: str = self.info[0]['user']['cover']['url']
        if mods is None:
            mods = []
        if mods:
            self._set_mods(mods)
            if self.mods_list:
                self.info = self.info[self.mods_list[0]]

        return self._get_all_score(self.info[0])

    def BestBPScore(self, min: int, max: int, mods=None) -> list:
        """
        返回 `BestBP` 成绩指定列表
        """
        if mods is None:
            mods = []
        self.bpList = []
        if mods:
            self._set_mods(mods, max)
            if self.mods_list:
                self.bpList = self.mods_list
        else:
            self.bpList = range(min - 1, max)

        return self.bpList

    def BestScore(self, bp: int):
        """
        返回 `BestBP` 成绩数据
        """
        self.map: dict = self.info[bp]['beatmapset']
        self.artist: str = self.map['artist_unicode'] if self.map['artist_unicode'] else self.map['artist']
        self.title: str = self.map['title_unicode'] if self.map['title_unicode'] else self.map['title']

        return self._get_all_score(self.info[bp])

    def new_bp_score(self) -> list:
        for num, i in enumerate(self.info):
            today = datetime.now().date()
            today_stamp = mktime(strptime(str(today), '%Y-%m-%d'))
            playtime = datetime.strptime(i['created_at'].replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S') + timedelta(
                hours=8)
            play_stamp = mktime(strptime(str(playtime), '%Y-%m-%d %H:%M:%S'))

            if play_stamp > today_stamp:
                self.bpList.append(num)

        return self.bpList


class Beatmapset:
    """
    地图信息
    """

    def __init__(self, info: dict):
        """
        返回地图数据
        """
        self.mode: int = info['mode_int']
        self.status: str = info['status']
        self.total_len: int = info['total_length']
        self.version: str = info['version']
        self.diff: float = info['difficulty_rating']
        self.od: float = info['accuracy']
        self.ar: float = info['ar']
        self.cs: float = info['cs']
        self.hp: float = info['drain']
        self.mapdiff: list = [self.cs, self.hp, self.od, self.ar, self.diff]
        self.bpm: float = info['bpm']
        self.c_circles: int = info['count_circles']
        self.c_sliders: int = info['count_sliders']
        self.setid: int = info['beatmapset_id']
        self.map: dict = info['beatmapset']
        self.maxcb: int = info['max_combo'] if self.mode != 3 else 0
        self.artist: str = self.map['artist_unicode'] if self.map['artist_unicode'] else self.map['artist']
        self.title: str = self.map['title_unicode'] if self.map['title_unicode'] else self.map['title']
        self.mapper: str = self.map['creator']
        self.uid: int = self.map['user_id']
        self.source: str = self.map['source'] if self.map['source'] else 'Nothing'
        self.cover: str = self.map['covers']['list@2x']
        self.music: str = self.map['preview_url']
        self.ranked_date: str = self.map['ranked_date']


class SayoInfo:
    def __init__(self, info: dict):
        """
        返回 SayoApi `map` 数据
        """
        self.setid: int = info['sid']
        self.title: str = info['titleU'] if info['titleU'] else info['title']
        self.artist: str = info['artistU'] if info['artistU'] else info['artist']
        self.mapper: str = info['creator']

    def map(self, info: dict):
        self.apptime = info['approved_date']
        self.source: str = info['source'] if info['source'] else 'Nothing'
        self.bpm: float = info['bpm']
        self.gmap: dict = info['bid_data']
        self.songlen: int = self.gmap[0]['length']

    def mapinfo(self, info: dict):
        self.diff: list = [info['CS'], info['HP'], info['OD'], info['AR']]
        self.bid: int = info['bid']
        self.maxcb: str = info['maxcombo']
        self.mode: int = info['mode']
        self.star: float = round(info['star'], 2)
        self.version: str = info['version']


class ChumiInfo(SayoInfo):

    def __init__(self, info: dict):
        """
        返回 ChumiApi `map` 数据
        """
        super().__init__(info)
        self.setid: int = info['SetID']
        self.title: str = info['Title']
        self.artist: str = info['Artist']
        self.mapper: str = info['Creator']