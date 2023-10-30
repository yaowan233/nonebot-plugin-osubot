from pathlib import Path
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
Torus_SemiBold_20 = ImageFont.truetype(
    str(osufile / "fonts" / "Torus SemiBold.otf"), 20
)
Torus_SemiBold_25 = ImageFont.truetype(
    str(osufile / "fonts" / "Torus SemiBold.otf"), 25
)
Torus_SemiBold_30 = ImageFont.truetype(
    str(osufile / "fonts" / "Torus SemiBold.otf"), 30
)
Torus_SemiBold_40 = ImageFont.truetype(
    str(osufile / "fonts" / "Torus SemiBold.otf"), 40
)
Torus_SemiBold_50 = ImageFont.truetype(
    str(osufile / "fonts" / "Torus SemiBold.otf"), 50
)
Venera_75 = ImageFont.truetype(str(osufile / "fonts" / "Venera.otf"), 75)

ColorPic = Image.open(osufile / "work" / "color.png").load()
InfoImg = Image.open(osufile / "info.png").convert("RGBA")
NewInfoImg = Image.open(osufile / "info_new.png").convert("RGBA")
SupporterBg = Image.open(osufile / "work" / "suppoter.png").convert("RGBA")
ExpLeftBg = Image.open(osufile / "work" / "left.png").convert("RGBA")
ExpCenterBg = Image.open(osufile / "work" / "center.png").convert("RGBA")
ExpRightBg = Image.open(osufile / "work" / "right.png").convert("RGBA")
BgImg = Image.open(osufile / "Best Performance.png").convert("RGBA")
BgImg1 = Image.open(osufile / "History Score.jpg").convert("RGBA")
MapBg = Image.open(osufile / "beatmapinfo.png").convert("RGBA")
BarImg = Image.open(osufile / "work" / "bmap.png").convert("RGBA")
