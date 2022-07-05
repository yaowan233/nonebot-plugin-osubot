from typing import List


class Mods:
    default = {
        '0': 'NO',
        '1': 'NF',
        '2': 'EZ',
        '4': 'TD',
        '8': 'HD',
        '16': 'HR',
        '32': 'SD',
        '64': 'DT',
        '128': 'RX',
        '256': 'HT',
        '576': 'NC',
        '1024': 'FL',
        '2048': 'AT',
        '4096': 'SO',
        '8192': 'RX2',
        '16384': 'PF',
        '32768': '4K',
        '65536': '5K',
        '131072': '6K',
        '262144': '7K',
        '524288': '8K',
        '1048576': 'FI',
        '2097152': 'RD',
        '4194304': 'Cinema',
        '8388608': 'TG',
        '16777216': '9K',
        '33554432': 'KC',
        '67108864': '1K',
        '134217728': '3K',
        '268435456': '2K',
        '536870912': 'V2',
        '1073741824': 'MR',
    }

    newmods = {value: key for key, value in default.items()}

    def __init__(self, info: dict, mods: list) -> None:
        self.info = info
        self.mods = mods

    def getmodslist(self) -> list:
        return self.__setmodslist__(self.info, self.__CalcMods__(self.mods))

    def __CalcMods__(self, mods: List[str]) -> int:
        num = 0
        for i in mods:
            setmodsnum = int(self.newmods[str(i.upper())])
            num += setmodsnum
        return num

    def __setmodslist__(self, info: dict, mods: int) -> list:
        vnum = []
        for i, play in enumerate(info):
            if play['mods']:
                num = self.__CalcMods__(play['mods'])
                if num == mods:
                    vnum.append(i)
        return vnum
