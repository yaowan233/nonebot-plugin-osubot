from pathlib import Path

import matplotlib as mpl
import matplotlib.colors as mcolors
import numpy as np
from PIL import Image, ImageFont

osufile = Path(__file__).parent.parent / "osufile"
Torus_Regular_20 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 20)
Torus_Regular_25 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 25)
Torus_Regular_30 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 30)
Torus_Regular_35 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 35)
Torus_Regular_40 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 40)
Torus_Regular_45 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 45)
Torus_Regular_50 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 50)
Torus_Regular_75 = ImageFont.truetype(str(osufile / "fonts" / "Torus Regular.otf"), 75)
Torus_SemiBold_20 = ImageFont.truetype(str(osufile / "fonts" / "Torus SemiBold.otf"), 20)
Torus_SemiBold_25 = ImageFont.truetype(str(osufile / "fonts" / "Torus SemiBold.otf"), 25)
Torus_SemiBold_30 = ImageFont.truetype(str(osufile / "fonts" / "Torus SemiBold.otf"), 30)
Torus_SemiBold_40 = ImageFont.truetype(str(osufile / "fonts" / "Torus SemiBold.otf"), 40)
Torus_SemiBold_45 = ImageFont.truetype(str(osufile / "fonts" / "Torus SemiBold.otf"), 45)
Torus_SemiBold_50 = ImageFont.truetype(str(osufile / "fonts" / "Torus SemiBold.otf"), 50)
Venera_75 = ImageFont.truetype(str(osufile / "fonts" / "Venera.otf"), 75)
extra_30 = ImageFont.truetype(str(osufile / "fonts" / "Extra.otf"), 30)

InfoImg = Image.open(osufile / "info.png").convert("RGBA")
SupporterBg = Image.open(osufile / "work" / "suppoter.png").convert("RGBA")
ExpLeftBg = Image.open(osufile / "work" / "left.png").convert("RGBA")
ExpCenterBg = Image.open(osufile / "work" / "center.png").convert("RGBA")
ExpRightBg = Image.open(osufile / "work" / "right.png").convert("RGBA")
BgImg = Image.open(osufile / "Best Performance.png").convert("RGBA")
BgImg1 = Image.open(osufile / "History Score.jpg").convert("RGBA")
MapBg = Image.open(osufile / "beatmapinfo.png").convert("RGBA")
MapBg1 = Image.open(osufile / "maniabeatmapinfo.png").convert("RGBA")
BarImg = Image.open(osufile / "work" / "bmap.png").convert("RGBA")
Stars = Image.open(osufile / "work" / "stars.png").convert("RGBA")
TeamBlue = Image.open(osufile / "match" / "team_blue.png").convert("RGBA")
TeamRed = Image.open(osufile / "match" / "team_red.png").convert("RGBA")
MpLink = Image.open(osufile / "match" / "mplink.png").convert("RGBA")
MpLinkMap = Image.open(osufile / "match" / "mplink_map.png").convert("RGBA")


# 颜色取色参考 https://github.com/ppy/osu-web/blob/97997d9c7b7f9c49f9b3cdd776c71afb9872c34b/resources/js/utils/beatmap-helper.ts#L20

__input_values = np.array([0.1, 1.25, 2, 2.5, 3.3, 4.2, 4.9, 5.8, 6.7, 7.7, 9])
__normalized_values = (__input_values - np.min(__input_values)) / (np.max(__input_values) - np.min(__input_values))

# 定义对应的颜色
__colors = [
    "#4290FB",
    "#4FC0FF",
    "#4FFFD5",
    "#7CFF4F",
    "#F6F05C",
    "#FF8068",
    "#FF4E6F",
    "#C645B8",
    "#6563DE",
    "#18158E",
    "#000000",
]

# 创建颜色映射对象
__cmap = mcolors.LinearSegmentedColormap.from_list(
    "difficultyColourSpectrum", list(zip(__normalized_values, __colors)), N=16384
)
__norm = mpl.colors.Normalize(vmin=0, vmax=9)
ColorArr = mpl.cm.ScalarMappable(norm=__norm, cmap=__cmap).to_rgba(np.linspace(0, 9, 900), bytes=True)
IconLs = ["\ue800", "\ue803", "\ue801", "\ue802"]
