GM = {0: "osu", 1: "taiko", 2: "fruits", 3: "mania"}
NGM = {"0": "osu", "1": "taiko", "2": "fruits", "3": "mania"}
GMN = {"osu": "Std", "taiko": "Taiko", "fruits": "Ctb", "mania": "Mania"}
FGM = {"osu": 0, "taiko": 1, "fruits": 2, "mania": 3}


def mods2list(args: str) -> list:
    args = args.replace(" ", "").replace(",", "").replace("，", "")
    args = args.upper()
    return [args[i : i + 2] for i in range(0, len(args), 2)]
