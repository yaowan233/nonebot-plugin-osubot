from __future__ import annotations


HELP_TOPICS = {
    "overview": (
        "OSUBot 指令帮助\n"
        "先使用 /bind <用户名、UID或主页链接> 绑定账号，再用 /info、/bp、/bl、/rl 等指令查询。\n"
        "通用格式：/命令 [玩家] [序号或范围]:[模式] [+Mods] [&sb]\n"
        "模式简称：o=osu!、t=taiko、c=catch、m=mania。\n"
        "可继续询问：绑定、模式、成绩、谱面、资料、多人、SB服，或“全部指令”。"
    ),
    "bind": (
        "账号绑定\n"
        "/bind <用户名、UID或主页链接>：绑定 osu! 账号\n"
        "/unbind：解除绑定\n"
        "示例：/bind peppy、/bind id:2、/bind https://osu.ppy.sh/users/2\n"
        "纯数字用户名会优先按用户名查找；需要明确使用 UID 时写 id:<UID>。"
    ),
    "mode": (
        "模式与版本\n"
        "/mode：查看当前默认模式\n"
        "/mode <模式>：修改默认模式，例如 /mode m\n"
        "/lazer（简写 /lz）：切换 stable / lazer 成绩\n"
        "简称：o/0=osu!，t/1=taiko，c/2=catch，m/3=mania。\n"
        "临时指定模式可写 /info:m、/bl:c；未指定时使用绑定账号的默认模式。"
    ),
    "score": (
        "成绩查询\n"
        "/bp [序号]：单条最佳成绩，例如 /bp 5\n"
        "/bl [起始-结束]：BP 列表，默认 1-30，例如 /bl 31-60\n"
        "/re [序号]、/rl [范围]：单条/列表最近游玩，包含未通过\n"
        "/pr [序号]、/pl [范围]：单条/列表最近通过成绩\n"
        "/sc [mapid]：指定谱面成绩；查询过谱面后可省略 mapid\n"
        "/nb [#天数]：最近新增 BP；/bpa：BP 分析；/hs [#天数]：PP/排名历史\n"
        "可附加玩家、模式和 Mods，例如 /bp peppy 5:o +HDHR。"
    ),
    "map": (
        "谱面工具\n"
        "/m [mapid] [+Mods]：单张难度信息\n"
        "/bm [setid]：谱面集信息\n"
        "/sc [mapid]：查询玩家在谱面上的成绩\n"
        "/bg [mapid]：获取背景；/预览 [mapid]:[模式]：生成预览\n"
        "/dl [setid]：下载谱面集；/倍速、/反键：谱面转换\n"
        "支持 osu! 谱面链接。先查询一张谱面后，/m、/bm、/sc、/bg、/预览、/dl 等可省略 ID，复用最近谱面。\n"
        "非 std 谱面会自动使用原生模式，不能强制转成其他模式。"
    ),
    "profile": (
        "账号资料与设置\n"
        "/info [玩家]:[模式]：玩家资料\n"
        "/mu：已绑定玩家主页；/update：刷新个人信息缓存\n"
        "/rank：群内 PP 排名；/推荐：个性化谱面推荐\n"
        "/setbg：设置个人背景；/clearbg：清除个人背景"
    ),
    "game": (
        "多人和其他功能\n"
        "/mp <matchid>：多人对局历史；/rt <matchid>：多人房评分\n"
        "/md <成就名>：查询 medal 获得方式\n"
        "/音频猜歌、/图片猜歌、/谱面猜歌：开始猜歌游戏"
    ),
    "sb": (
        "ppysb 服务器查询\n"
        "/sbbind <玩家>：绑定 ppysb；/sbunbind：解除绑定\n"
        "在普通查询末尾添加 &sb，例如 /info &sb、/bl:4 &sb、/rl:5 &sb、/sc <mapid>:6 &sb。\n"
        "模式 0/1/2/3：std/taiko/catch/mania；4/5/6：RX std/taiko/catch；8：AP std。"
    ),
}

TOPIC_ALIASES = {
    "help": "overview",
    "帮助": "overview",
    "概览": "overview",
    "绑定": "bind",
    "账号": "bind",
    "模式": "mode",
    "lazer": "mode",
    "成绩": "score",
    "bp": "score",
    "recent": "score",
    "最近": "score",
    "谱面": "map",
    "地图": "map",
    "beatmap": "map",
    "资料": "profile",
    "设置": "profile",
    "用户": "profile",
    "多人": "game",
    "比赛": "game",
    "match": "game",
    "游戏": "game",
    "ppysb": "sb",
    "sb服": "sb",
}

TOPIC_LABELS = "overview、bind、mode、score、map、profile、game、sb、all"


def get_command_help(topic: str | None = "overview") -> str:
    """Return exact manual command help for matchers and LLM tools."""
    normalized = (topic or "overview").strip().lower()
    normalized = TOPIC_ALIASES.get(normalized, normalized)
    if normalized in {"all", "全部", "完整", "所有指令"}:
        return "\n\n".join(HELP_TOPICS[name] for name in HELP_TOPICS if name != "overview")
    if normalized in HELP_TOPICS:
        return HELP_TOPICS[normalized]
    return f"没有找到该帮助主题。可用主题：{TOPIC_LABELS}。"
