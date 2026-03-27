"""纯逻辑单元测试：mods.py / utils/__init__.py / beatmap_stats_moder.py"""

from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# mods.py
# ---------------------------------------------------------------------------


def test_get_mods_no_flag():
    """mods=0 时只返回 CL。"""
    from nonebot_plugin_osubot.mods import get_mods

    result = get_mods(0)
    assert len(result) == 1
    assert result[0].acronym == "CL"


def test_get_mods_hd_dt():
    """HD|DT 时返回 HD、DT、CL。"""
    from nonebot_plugin_osubot.mods import get_mods, mods_dic

    result = get_mods(mods_dic["HD"] | mods_dic["DT"])
    acronyms = {m.acronym for m in result}
    assert "HD" in acronyms
    assert "DT" in acronyms
    assert "CL" in acronyms


def test_get_mods_all_flags():
    """所有 bit 置 1 时，CL 总是追加在末尾。"""
    from nonebot_plugin_osubot.mods import get_mods

    result = get_mods(0xFFFFFFFF)
    assert result[-1].acronym == "CL"
    assert len(result) > 1


def test_get_mods_list_no_filter():
    """mods=[] 时返回全部下标。"""
    from nonebot_plugin_osubot.mods import get_mods_list

    scores = [MagicMock() for _ in range(4)]
    assert get_mods_list(scores, []) == [0, 1, 2, 3]


def test_get_mods_list_with_filter():
    """只返回包含指定 mod 的成绩下标。"""
    from nonebot_plugin_osubot.mods import get_mods_list
    from nonebot_plugin_osubot.schema.score import Mod

    s_hd_dt = MagicMock()
    s_hd_dt.mods = [Mod(acronym="HD"), Mod(acronym="DT")]
    s_hd = MagicMock()
    s_hd.mods = [Mod(acronym="HD")]
    s_none = MagicMock()
    s_none.mods = None

    assert get_mods_list([s_hd_dt, s_hd, s_none], ["HD"]) == [0, 1]
    assert get_mods_list([s_hd_dt, s_hd, s_none], ["HD", "DT"]) == [0]
    assert get_mods_list([s_hd_dt, s_hd, s_none], ["NM"]) == []


def test_get_mods_list_no_scores():
    """空列表返回空列表。"""
    from nonebot_plugin_osubot.mods import get_mods_list

    assert get_mods_list([], ["HD"]) == []


def test_calc_mods_empty():
    """空 mods 列表返回 0。"""
    from nonebot_plugin_osubot.mods import calc_mods

    assert calc_mods([]) == 0


def test_calc_mods_known_values():
    """HD ^ DT 异或结果正确。"""
    from nonebot_plugin_osubot.mods import calc_mods, mods_dic
    from nonebot_plugin_osubot.schema.score import Mod

    result = calc_mods([Mod(acronym="HD"), Mod(acronym="DT")])
    assert result == mods_dic["HD"] ^ mods_dic["DT"]


def test_calc_mods_unknown_acronym():
    """未知 acronym 视为 0，不影响结果。"""
    from nonebot_plugin_osubot.mods import calc_mods, mods_dic
    from nonebot_plugin_osubot.schema.score import Mod

    result = calc_mods([Mod(acronym="HD"), Mod(acronym="XX")])
    assert result == mods_dic["HD"]


# ---------------------------------------------------------------------------
# utils/__init__.py  —  mods2list
# ---------------------------------------------------------------------------


def test_mods2list_basic():
    from nonebot_plugin_osubot.utils import mods2list

    assert mods2list("HDDT") == ["HD", "DT"]


def test_mods2list_lowercase():
    from nonebot_plugin_osubot.utils import mods2list

    assert mods2list("hddt") == ["HD", "DT"]


def test_mods2list_with_separators():
    """空格、逗号、中文逗号均被移除。"""
    from nonebot_plugin_osubot.utils import mods2list

    assert mods2list("hd, dt") == ["HD", "DT"]
    assert mods2list("hd，dt") == ["HD", "DT"]
    assert mods2list("hd dt") == ["HD", "DT"]


def test_mods2list_empty():
    from nonebot_plugin_osubot.utils import mods2list

    assert mods2list("") == []


def test_mods2list_single():
    from nonebot_plugin_osubot.utils import mods2list

    assert mods2list("HR") == ["HR"]


# ---------------------------------------------------------------------------
# beatmap_stats_moder.py
# ---------------------------------------------------------------------------


def _make_beatmap(cs=4.0, ar=9.0, od=8.0, hp=5.0, bpm=200.0, length=100.0, mode="osu"):
    """with_mods は属性の読み書きだけなので MagicMock で十分。"""
    bmap = MagicMock()
    bmap.cs = cs
    bmap.ar = ar
    bmap.accuracy = od  # schema 上 OD は accuracy フィールド
    bmap.drain = hp
    bmap.bpm = bpm
    bmap.total_length = length
    bmap.mode = mode
    return bmap


def test_modify_ar_below5():
    """AR < 5 时走第一条公式分支。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import modify_ar

    result = modify_ar(3.0, 1.0, 1.0)
    assert 0 <= result <= 10


def test_modify_ar_above5():
    """AR >= 5 时走第二条公式分支。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import modify_ar

    result = modify_ar(8.0, 1.0, 1.0)
    assert abs(result - 8.0) < 0.01


def test_modify_ar_with_dt():
    """DT 加速后 AR 变大。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import modify_ar

    ar_normal = modify_ar(8.0, 1.0, 1.0)
    ar_dt = modify_ar(8.0, 1.5, 1.0)
    assert ar_dt > ar_normal


def test_modify_od_identity():
    """speed_mul=1, multiplier=1 时 OD 不变。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import modify_od

    assert abs(modify_od(8.0, 1.0, 1.0) - 8.0) < 0.01


def test_modify_od_with_hr():
    """HR multiplier=1.4 使 OD 变难（更大）。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import modify_od

    assert modify_od(8.0, 1.0, 1.4) > 8.0


def test_with_mods_no_mods():
    """无 mod 时谱面属性不变。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import with_mods

    bmap = _make_beatmap(ar=9.0, od=8.0, bpm=200.0)
    result = with_mods(bmap, None, [])
    assert abs(result.ar - 9.0) < 0.01
    assert abs(result.accuracy - 8.0) < 0.01
    assert abs(result.bpm - 200.0) < 0.01


def test_with_mods_dt():
    """DT 使 BPM 变为 1.5x，AR 提升。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import with_mods
    from nonebot_plugin_osubot.schema.score import Mod

    bmap = _make_beatmap(ar=9.0, bpm=200.0, length=100.0)
    result = with_mods(bmap, None, [Mod(acronym="DT")])
    assert abs(result.bpm - 300.0) < 0.01
    assert abs(result.total_length - 100.0 / 1.5) < 0.01
    assert result.ar > 9.0


def test_with_mods_ht():
    """HT 使 BPM 变为 0.75x，AR 降低。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import with_mods
    from nonebot_plugin_osubot.schema.score import Mod

    bmap = _make_beatmap(ar=8.0, bpm=200.0, length=100.0)
    result = with_mods(bmap, None, [Mod(acronym="HT")])
    assert abs(result.bpm - 150.0) < 0.01
    assert result.ar < 8.0


def test_with_mods_hr():
    """HR 使 CS 提升（×1.3），HP/OD 提升。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import with_mods
    from nonebot_plugin_osubot.schema.score import Mod

    bmap = _make_beatmap(cs=4.0, hp=5.0)
    result = with_mods(bmap, None, [Mod(acronym="HR")])
    assert abs(result.cs - min(10.0, 4.0 * 1.3)) < 0.01
    assert result.drain > 5.0


def test_with_mods_ez():
    """EZ 使 CS 减半，HP/OD 降低。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import with_mods
    from nonebot_plugin_osubot.schema.score import Mod

    bmap = _make_beatmap(cs=4.0, hp=5.0)
    result = with_mods(bmap, None, [Mod(acronym="EZ")])
    assert abs(result.cs - 2.0) < 0.01
    assert result.drain < 5.0


def test_with_mods_mania_ignores_speed():
    """mania 模式下 DT 不影响 speed_mul（OD 计算用 speed=1）。"""
    from nonebot_plugin_osubot.beatmap_stats_moder import with_mods
    from nonebot_plugin_osubot.schema.score import Mod

    bmap_mania = _make_beatmap(od=8.0, bpm=200.0, length=100.0, mode="mania")
    result = with_mods(bmap_mania, None, [Mod(acronym="DT")])
    # mania 模式重置 speed_mul=1，OD 不受速度影响
    assert abs(result.accuracy - 8.0) < 0.01
