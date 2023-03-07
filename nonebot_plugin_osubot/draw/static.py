from pathlib import Path
from PIL import Image

osufile = Path(__file__).parent.parent / 'osufile'
Torus_Regular = osufile / 'fonts' / 'Torus Regular.otf'
Torus_SemiBold = osufile / 'fonts' / 'Torus SemiBold.otf'
Venera = osufile / 'fonts' / 'Venera.otf'
ColorPic = Image.open(osufile / 'work' / 'color.png').load()
InfoImg = Image.open(osufile / 'info.png').convert('RGBA')
NewInfoImg = Image.open(osufile / 'info_new.png').convert('RGBA')
SupporterBg = Image.open(osufile / 'work' / 'suppoter.png').convert('RGBA')
ExpLeftBg = Image.open(osufile / 'work' / 'left.png').convert('RGBA')
ExpCenterBg = Image.open(osufile / 'work' / 'center.png').convert('RGBA')
ExpRightBg = Image.open(osufile / 'work' / 'right.png').convert('RGBA')
BgImg = Image.open(osufile / 'Best Performance.png').convert('RGBA')
MapBg = Image.open(osufile / 'beatmapinfo.png').convert('RGBA')
BarImg = Image.open(osufile / 'work' / 'bmap.png').convert('RGBA')
