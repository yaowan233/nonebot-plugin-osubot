GM = {0: 'osu', 1: 'taiko', 2: 'fruits', 3: 'mania'}
NGM = {'0': 'osu', '1': 'taiko', '2': 'fruits', '3': 'mania'}
GMN = {'osu': 'Std', 'taiko': 'Taiko', 'fruits': 'Ctb', 'mania': 'Mania'}
FGM = {'osu': 0, 'taiko': 1, 'fruits': 2, 'mania': 3}


def mods2list(args: str) -> list:
    if '，' in args:
        sep = '，'
    elif ',' in args:
        sep = ','
    else:
        sep = ' '
    args = args.upper()
    return args.split(sep)
