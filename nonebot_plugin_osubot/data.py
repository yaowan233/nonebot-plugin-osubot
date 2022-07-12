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