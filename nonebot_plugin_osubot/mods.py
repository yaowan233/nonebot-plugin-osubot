from typing import List
from .schema import Score

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

new_mods = {value: key for key, value in default.items()}


def get_mods_list(score_ls: List[Score], mods: List[str]) -> List[int]:
    if not mods:
        return list(range(len(score_ls)))
    mods_index_ls = []
    for i, score in enumerate(score_ls):
        if score.mods and validate_mods(score, mods):
            mods_index_ls.append(i)
    return mods_index_ls


def calc_mods(mods: List[str]) -> int:
    num = 0
    for i in mods:
        mod_num = int(new_mods[str(i.upper())])
        num += mod_num
    return num


def validate_mods(score: Score, mods: List[str]) -> bool:
    return calc_mods(score.mods) == calc_mods(mods)
