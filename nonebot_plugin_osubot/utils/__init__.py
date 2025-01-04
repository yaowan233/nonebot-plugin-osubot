GM = {0: "osu", 1: "taiko", 2: "fruits", 3: "mania", 4: "osu", 5: "taiko", 6: "fruits"}
NGM = {
    "0": "osu",
    "1": "taiko",
    "2": "fruits",
    "3": "mania",
    "4": "rxosu",
    "5": "rxtaiko",
    "6": "rxfruits",
}
GMN = {
    "osu": "Std",
    "taiko": "Taiko",
    "fruits": "Ctb",
    "mania": "Mania",
    "rxosu": "RX Std",
    "rxtaiko": "RX Taiko",
    "rxfruits": "RX Ctb",
}
FGM = {"osu": 0, "taiko": 1, "fruits": 2, "mania": 3, "rxosu": 4, "rxtaiko": 5, "rxfruits": 6}


def mods2list(args: str) -> list:
    args = args.replace(" ", "").replace(",", "").replace("，", "")
    args = args.upper()
    return [args[i : i + 2] for i in range(0, len(args), 2)]
