"""Native SVG renderer for the fixed 1440x900 single-score card."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

import asyncio
import base64
from contextvars import ContextVar
from dataclasses import dataclass
from io import BytesIO
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .svg_components import mod_strip
from .svg_render import FONT_FAMILY, escape_text, fit_text, font_for_text, render_svg_png


WIDTH = 1440
HEIGHT = 900
PINK = "#ff4f96"
CYAN = "#4ce1e7"
PURPLE = "#9f7cff"


@dataclass(frozen=True, slots=True)
class _TextSpec:
    x: float
    y: float
    value: str
    size: int
    fill: str
    anchor: str
    opacity: float


@dataclass(frozen=True, slots=True)
class _ImageSpec:
    uri: str
    x: int
    y: int
    width: int
    height: int
    contain: bool
    circle: bool
    border_width: int


_active_text_layer: ContextVar[list[_TextSpec] | None] = ContextVar("score_svg_text_layer", default=None)
_active_image_layer: ContextVar[list[_ImageSpec] | None] = ContextVar("score_svg_image_layer", default=None)


def _attr(value: object) -> str:
    return escape_text(value)


def _text(
    x: float,
    y: float,
    value: object,
    size: int,
    *,
    fill: str = "#ffffff",
    weight: int = 400,
    anchor: str = "start",
    opacity: float = 1,
) -> str:
    text_layer = _active_text_layer.get()
    if text_layer is not None:
        text_layer.append(_TextSpec(x, y, str(value), size, fill, anchor, opacity))
        return ""
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT_FAMILY}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill}" opacity="{opacity}">'
        f"{escape_text(value)}</text>"
    )


def _image(uri: str | None, x: int, y: int, width: int, height: int, *, clip: str | None = None) -> str:
    if not uri:
        return ""
    clip_attr = f' clip-path="url(#{clip})"' if clip else ""
    return (
        f'<image href="{_attr(uri)}" x="{x}" y="{y}" width="{width}" height="{height}" '
        f'preserveAspectRatio="xMidYMid slice"{clip_attr}/>'
    )


def _queue_pillow_image(
    uri: str | None,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    contain: bool = False,
    circle: bool = False,
    border_width: int = 0,
) -> str:
    image_layer = _active_image_layer.get()
    if uri and image_layer is not None:
        image_layer.append(_ImageSpec(uri, x, y, width, height, contain, circle, border_width))
    return ""


def _text_width(value: object, size: int) -> float:
    return font_for_text(value, size).getlength(str(value))


def _supporter_hearts(x: float, y: float, level: int) -> str:
    """Draw touching heart glyphs without font side bearings between them."""
    parts = []
    for index in range(level):
        left = x + index * 8
        parts.append(
            f'<path d="M{left + 4.5} {y + 8.5}'
            f"C{left + 3.8} {y + 7.7} {left} {y + 5.4} {left} {y + 2.8}"
            f"C{left} {y + 0.9} {left + 1.4} {y} {left + 2.8} {y}"
            f"C{left + 3.8} {y} {left + 4.5} {y + 0.7} {left + 4.5} {y + 1.4}"
            f"C{left + 4.5} {y + 0.7} {left + 5.2} {y} {left + 6.2} {y}"
            f"C{left + 7.6} {y} {left + 9} {y + 0.9} {left + 9} {y + 2.8}"
            f'C{left + 9} {y + 5.4} {left + 5.2} {y + 7.7} {left + 4.5} {y + 8.5}Z" fill="#fff"/>'
        )
    return "".join(parts)


def _star_colour(value: object) -> str:
    try:
        stars = float(value)
    except (TypeError, ValueError):
        return "#000000"
    stops = (
        (0.1, "#4290fb"),
        (1.25, "#4fc0ff"),
        (2.0, "#4fffd5"),
        (2.5, "#7cff4f"),
        (3.3, "#f6f05c"),
        (4.2, "#ff8068"),
        (4.9, "#ff4e6f"),
        (5.8, "#c645b8"),
        (6.7, "#6563de"),
        (7.7, "#18158e"),
        (9.0, "#000000"),
    )
    if stars < 0.1:
        return "#aaaaaa"
    if stars >= 9:
        return "#000000"
    for (left, left_colour), (right, right_colour) in zip(stops, stops[1:]):
        if stars <= right:
            ratio = max(0.0, min(1.0, (stars - left) / (right - left)))
            left_rgb = tuple(int(left_colour[index : index + 2], 16) for index in (1, 3, 5))
            right_rgb = tuple(int(right_colour[index : index + 2], 16) for index in (1, 3, 5))
            rgb = tuple(round(a * (1 - ratio) + b * ratio) for a, b in zip(left_rgb, right_rgb))
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    return "#000000"


def _decode_data_uri(uri: str) -> bytes:
    _header, encoded = uri.split(",", 1)
    return base64.b64decode(encoded)


@lru_cache(maxsize=32)
def _background_jpeg(cover_uri: str) -> bytes:
    """Cache only the map artwork treatment, never a rendered score card."""
    with Image.open(BytesIO(_decode_data_uri(cover_uri))) as source:
        background = ImageOps.fit(source.convert("RGB"), (720, 450), method=Image.Resampling.BILINEAR)
    background = background.filter(ImageFilter.GaussianBlur(7))
    background = ImageEnhance.Color(background).enhance(1.15)
    background = ImageEnhance.Brightness(background).enhance(0.55)
    result = BytesIO()
    background.save(result, "JPEG", quality=72)
    background.close()
    return result.getvalue()


def _render_identity(data: dict) -> str:
    username = str(data.get("username") or "")
    support_level = max(0, int(data.get("support_level") or 0))
    supporter_width = 12 + support_level * 8 if support_level else 0
    username_max_width = 191 - (supporter_width + 8 if support_level else 0)
    username_size = fit_text(username, username_max_width, 20, 13)
    username_width = min(username_max_width, _text_width(username, username_size))
    parts = [
        '<rect x="47" y="553" width="300" height="310" fill="#111925f2"/>',
        '<circle cx="92" cy="612" r="34" fill="#4ce1e72d"/>',
        _image(data.get("avatar"), 63, 583, 58, 58, clip="player-avatar"),
        _text(136, 604, username, username_size, weight=700),
        _text(136, 625, f"UID {data.get('user_id', '')} · {data.get('country', '')}", 11, fill="#ffffff99"),
    ]
    if support_level:
        supporter_x = 136 + username_width + 8
        parts.extend(
            [
                f'<rect x="{supporter_x}" y="585" width="{supporter_width}" height="20" rx="10" fill="#e93689"/>',
                _supporter_hearts(
                    supporter_x + (supporter_width - (support_level * 8 + 1)) / 2,
                    591,
                    support_level,
                ),
            ]
        )
    team = data.get("team") or {}
    if team:
        parts.extend(
            [
                _image(team.get("icon"), 136, 632, 24, 14),
                _text(166, 644, f"[{team.get('short_name', '')}] {team.get('name', '')}", 10, fill="#ffffff99"),
            ]
        )

    stat_values = (
        ("全球排名", f"#{data['global_rank']}" if data.get("global_rank") else "—"),
        ("地区排名", f"#{data['country_rank']}" if data.get("country_rank") else "—"),
        (data.get("profile_third_label", "玩家等级"), data.get("profile_third_value", "—")),
    )
    parts.append('<path d="M67 671H327M67 727H327" stroke="#ffffff20"/>')
    for index, (label, value) in enumerate(stat_values):
        x = 68 + index * 86
        if index:
            parts.append(f'<path d="M{x - 8} 671V727" stroke="#ffffff16"/>')
        parts.extend([_text(x, 691, label, 10, fill="#ffffff88"), _text(x, 715, value, 16, weight=700)])

    owners = list(data.get("owners") or [])[:8]
    parts.append(_text(68, 752, "谱师" if len(owners) == 1 else f"合作谱师 · {len(owners)} 人", 11, fill=CYAN))
    for index, owner in enumerate(owners):
        if len(owners) == 1:
            x, y, avatar_size, text_x, text_y, text_size = 68, 766, 44, 122, 794, 16
        else:
            column = index % 2
            row = index // 2
            x = 68 + column * 132
            y = 766 + row * 25
            avatar_size, text_x, text_y, text_size = 23, x + 30, y + 17, 11
        parts.append(
            _queue_pillow_image(
                owner.get("avatar"),
                x,
                y,
                avatar_size,
                avatar_size,
                circle=True,
                border_width=2 if len(owners) == 1 else 1,
            )
        )
        parts.append(
            _text(
                text_x,
                text_y,
                owner.get("username", ""),
                text_size,
                fill="#ffffffdd",
            )
        )
    return "".join(parts)


def _render_judgements(data: dict) -> str:
    left = 347
    parts = [
        f'<rect x="{left}" y="553" width="341" height="310" fill="#111925ed"/>',
        _text(left + 24, 592, "判定明细", 20, weight=700),
    ]
    judgements = list(data.get("judgements") or [])
    columns = max(2, min(3, int(data.get("judge_cols") or 2)))
    for index, item in enumerate(judgements):
        column = index % columns
        row = index // columns
        cell_width = 292 / columns
        x = left + 24 + column * cell_width
        y = 626 + row * 69
        colour = (CYAN, PURPLE, PINK)[column % 3]
        parts.extend(
            [
                f'<rect x="{x}" y="{y}" width="2" height="48" fill="{colour}"/>',
                _text(x + 11, y + 14, item.get("label", ""), 11, fill="#ffffff99"),
                _text(
                    x + 11,
                    y + 43,
                    item.get("display", "0"),
                    27,
                    fill="#ffffff70" if not item.get("value") else "#ffffff",
                    weight=700,
                ),
            ]
        )
    summary = (
        ("总判定", data.get("judgement_total", "0"), CYAN),
        ("失误率", data.get("miss_rate", "0%"), PINK),
        ("连击完成", data.get("combo_completion", "0%"), PURPLE),
    )
    for index, (label, value, colour) in enumerate(summary):
        x = left + 24 + index * 97
        parts.extend(
            [
                f'<rect x="{x}" y="802" width="97" height="3" fill="{colour}"/>',
                f'<rect x="{x}" y="805" width="97" height="45" fill="#09121d99"/>',
                _text(x + 8, 823, label, 10, fill=colour),
                _text(x + 8, 843, value, 16, weight=700),
            ]
        )
    return "".join(parts)


def _render_dimensions(data: dict) -> str:
    left = 688
    parts = [
        f'<rect x="{left}" y="553" width="334" height="310" fill="#111925e9"/>',
        _text(left + 24, 592, "谱面参数", 20, weight=700),
        _text(left + 82, 622, "0", 10, fill="#ffffff88"),
        _text(left + 176, 622, "5", 10, fill="#ffffff88", anchor="middle"),
        _text(left + 270, 622, data.get("dimension_max", 10), 10, fill="#ffffff88", anchor="end"),
        _text(left + 310, 622, "当前", 10, fill="#ffffff88", anchor="end"),
    ]
    for index, item in enumerate(data.get("dimensions") or []):
        y = 651 + index * 49
        start = left + 82
        end = left + 270
        current = start + (end - start) * float(item.get("current_pos") or 0) / 100
        original = start + (end - start) * float(item.get("original_pos") or 0) / 100
        changed = bool(item.get("changed"))
        parts.extend(
            [
                f'<path d="M{start} {y}H{end}" stroke="#ffffff40"/>',
                _text(left + 24, y + 5, item.get("name", ""), 13, weight=700),
                f'<rect x="{current - 5}" y="{y - 5}" width="10" height="10" '
                f'fill="{PINK if changed else CYAN}" transform="rotate(45 {current} {y})"/>',
                _text(
                    left + 310,
                    y + 6,
                    item.get("current", ""),
                    18,
                    weight=700,
                    anchor="end",
                    fill=PINK if changed else "#ffffff",
                ),
            ]
        )
        if changed:
            parts.extend(
                [
                    f'<circle cx="{original}" cy="{y}" r="4" fill="#111925" stroke="{CYAN}" stroke-width="2"/>',
                    _text(original, y - 10, item.get("original", ""), 9, fill=CYAN, anchor="middle"),
                ]
            )
    return "".join(parts)


def _render_pp(data: dict) -> str:
    left = 1022
    width = 376
    parts = [
        f'<rect x="{left}" y="553" width="{width}" height="310" fill="#111925e7"/>',
        _text(left + 24, 592, "PP 构成" if data.get("pp_components") else "PP 数据", 20, weight=700),
    ]
    if data.get("pp_has_breakdown"):
        total_pp = str(data.get("total_pp") or "0")
        right = left + 352
        suffix_width = _text_width("pp", 11)
        value_right = right - suffix_width - 4
        label_right = value_right - _text_width(total_pp, 23) - 9
        parts.extend(
            [
                _text(label_right, 592, "总 PP", 11, fill="#ffffffb0", anchor="end"),
                _text(value_right, 592, total_pp, 23, weight=700, anchor="end"),
                _text(right, 592, "pp", 11, fill=PINK, weight=700, anchor="end"),
            ]
        )
    components = list(data.get("pp_components") or data.get("pp_items") or [])
    count = max(1, len(components))
    cell_width = 328 / count
    for index, item in enumerate(components):
        x = left + 24 + index * cell_width
        colour = (CYAN, PURPLE, PINK)[index % 3]
        parts.extend(
            [
                f'<rect x="{x}" y="618" width="{cell_width}" height="74" fill="#09121d99" stroke="#ffffff18"/>',
                f'<rect x="{x}" y="618" width="{cell_width}" height="3" fill="{colour}"/>',
                _text(x + 10, 644, item.get("label", ""), 11, fill=colour),
                _text(x + 10, 677, f"{item.get('value', '0')} pp", 19, weight=700),
            ]
        )
    parts.append(_text(left + 24, 725, data.get("pp_target_title", "准确率推演"), 11, fill="#ffffff99"))
    targets = list(data.get("pp_targets") or [])
    target_width = 328 / max(1, min(4, len(targets)))
    for index, item in enumerate(targets):
        column = index % 4
        row = index // 4
        x = left + 24 + column * target_width
        y = 742 + row * 54
        colour = (CYAN, PURPLE, PINK, "#ffd966")[column]
        parts.extend(
            [
                f'<rect x="{x}" y="{y}" width="{target_width}" height="52" fill="#09121da8" stroke="#ffffff18"/>',
                f'<rect x="{x}" y="{y}" width="2" height="52" fill="{colour}"/>',
                _text(x + 8, y + 19, item.get("label", ""), 9, fill=colour),
                _text(x + 8, y + 42, f"{item.get('value', '0')} pp", 15, weight=700),
            ]
        )
    return "".join(parts)


def build_score_svg(data: dict) -> str:
    title = str(data.get("title") or "")
    artist = str(data.get("artist") or "")
    version = str(data.get("version") or "")
    score = str(data.get("score") or "0")
    title_size = fit_text(title, 640, 54, 30)
    artist_size = fit_text(artist, 300, 18, 12)
    score_size = fit_text(score, 620, 78, 50)
    star_colour = _star_colour(data.get("stars"))
    star_text = "#101925" if float(data.get("stars") or 0) < 6.5 else "#ffd966"

    mod_items = [
        item
        for item in list(data.get("mods") or [])
        if str(item.get("name") or "").upper() != "NM"
    ][:8]
    mod_names = [str(item.get("name") or "") for item in mod_items]
    speed_changes = {
        name: str(item["speed_change"])
        for name, item in zip(mod_names, mod_items)
        if item.get("speed_change")
    }
    mods_svg = mod_strip(
        mod_names,
        speed_changes,
        x=408,
        y=226,
        icon_size=36,
        max_width=560,
        preserve_artwork_ratio=True,
        text_renderer=_text,
    )

    score_version = data.get("score_version")
    version_badge = ""
    if score_version:
        badge_text = "Lazer" if score_version == "lazer" else "Stable"
        badge_colour = PURPLE if score_version == "lazer" else PINK
        version_badge = (
            f'<rect x="1103" y="39" width="58" height="22" rx="11" fill="{badge_colour}33" stroke="{badge_colour}"/>'
            + _text(1132, 54, badge_text, 10, fill=badge_colour, weight=700, anchor="middle")
        )

    mode_label = f"单曲成绩 / {data.get('mode_name', '')}"
    date_label = f"{data.get('ended_at', '')} · {data.get('status', '')}"
    pp_label = f"{data.get('pp', '0')}pp"
    accuracy_label = f"{data.get('accuracy', '0')}%"
    map_label = f"{data.get('status', '')} · {data.get('map_id', '')}"
    star_label = f"★ {data.get('stars', '0')}"
    bpm_label = f"{data.get('bpm', '--')} BPM"
    artist_width = min(300, _text_width(artist, artist_size))
    version_x = round(408 + artist_width + 12)
    version_width = round(max(90, min(260, _text_width(version, 13) + 24)))
    identity_svg = _render_identity(data)
    judgements_svg = _render_judgements(data)
    dimensions_svg = _render_dimensions(data)
    pp_svg = _render_pp(data)

    rank_image = _queue_pillow_image(data.get("rank_image"), 1018, 91, 350, 390, contain=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <linearGradient id="shade" x1="0" x2="1"><stop stop-color="#07101dfc" offset="0"/><stop stop-color="#07101d92" offset=".58"/><stop stop-color="#07101de8" offset="1"/></linearGradient>
  <linearGradient id="aurora"><stop stop-color="#4ce1e720"/><stop offset=".55" stop-color="#9f7cff14"/><stop offset="1" stop-color="#ff4f9630"/></linearGradient>
  <clipPath id="cover"><rect x="47" y="170" width="294" height="170" rx="2"/></clipPath>
  <clipPath id="player-avatar"><circle cx="92" cy="612" r="29"/></clipPath>
  <filter id="rank-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="12" stdDeviation="10" flood-color="#000000" flood-opacity=".65"/></filter>
</defs>
<rect width="1440" height="900" fill="url(#shade)"/>
<rect width="1440" height="900" fill="url(#aurora)"/>
<path d="M47 78H1398" stroke="#ffffff28"/>
{_text(47, 49, "OSU!", 13, fill=PINK, weight=700)}
{_text(88, 49, mode_label, 13, weight=700)}
{version_badge}
{_text(1398, 54, date_label, 11, fill="#ffffffaa", anchor="end")}

{_text(408, 147, title, title_size, weight=700)}
{_text(408, 184, artist, artist_size, fill="#ffffffb5", weight=700)}
<rect x="{version_x}" y="158" width="{version_width}" height="30" fill="#08101bc9" stroke="#ffffff30"/>
<rect x="{version_x}" y="158" width="4" height="30" fill="{PINK}"/>
{_text(version_x + 14, 179, version, 13, weight=700)}
{mods_svg}
{_text(408, 345, score, score_size, weight=700)}
{_text(408, 382, "本次表现", 11, fill="#ffffff88")}
{_text(408, 416, pp_label, 28, weight=700)}
{_text(560, 382, "准确率", 11, fill="#ffffff88")}
{_text(560, 416, accuracy_label, 28, weight=700)}
{_text(730, 382, "最大连击", 11, fill="#ffffff88")}
{_text(730, 416, data.get("combo", "0x"), 28, fill=CYAN if data.get("combo_is_full") else "#ffffff", weight=700)}

<rect x="61" y="184" width="294" height="170" fill="{PINK}"/>
{_image(data.get("cover"), 47, 170, 294, 170, clip="cover")}
<rect x="57" y="306" width="142" height="25" fill="#07101ddd"/>
{_text(67, 324, map_label, 10, weight=700)}
<rect x="253" y="180" width="78" height="28" rx="14" fill="{star_colour}" stroke="#ffffff77"/>
{_text(292, 200, star_label, 14, fill=star_text, weight=700, anchor="middle")}
<rect x="47" y="363" width="294" height="61" fill="#08101b9e" stroke="#ffffff20"/>
<path d="M120 363V424M194 363V424M267 363V424" stroke="#ffffff18"/>
{_text(57, 383, "速度", 10, fill="#ffffff88")}{_text(57, 407, bpm_label, 15, weight=700)}
{_text(130, 383, "长度", 10, fill="#ffffff88")}{_text(130, 407, data.get("length", "--"), 15, weight=700)}
{_text(204, 383, "物件", 10, fill="#ffffff88")}{_text(204, 407, data.get("objects", "--"), 15, weight=700)}
{_text(277, 383, "谱面 ID", 10, fill="#ffffff88")}{_text(277, 407, data.get("map_id", "--"), 13, weight=700)}

{rank_image}

<rect x="47" y="549" width="1351" height="4" fill="#4ce1e7"/>
<rect x="347" y="549" width="341" height="4" fill="#ff4f96"/>
<rect x="688" y="549" width="334" height="4" fill="#9f7cff"/>
<rect x="1022" y="549" width="376" height="4" fill="#ffd966"/>
{identity_svg}
{judgements_svg}
{dimensions_svg}
{pp_svg}
<rect x="47" y="553" width="1351" height="310" fill="none" stroke="#ffffff26"/>
<path d="M347 553V863M688 553V863M1022 553V863" stroke="#ffffff20"/>
</svg>"""
    return svg


def _render_score_svg_sync(data: dict) -> BytesIO:
    text_layer: list[_TextSpec] = []
    image_layer: list[_ImageSpec] = []
    token = _active_text_layer.set(text_layer)
    image_token = _active_image_layer.set(image_layer)
    try:
        svg = build_score_svg(data)
    finally:
        _active_text_layer.reset(token)
        _active_image_layer.reset(image_token)
    overlay = render_svg_png(svg, width=WIDTH, height=HEIGHT)

    with Image.open(BytesIO(_background_jpeg(str(data["cover"])))) as small_background:
        background = small_background.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR).convert("RGBA")
    with Image.open(BytesIO(overlay)) as foreground:
        background.alpha_composite(foreground.convert("RGBA"))

    for item in image_layer:
        with Image.open(BytesIO(_decode_data_uri(item.uri))) as source:
            rgba = source.convert("RGBA")
            if item.contain:
                frame = ImageOps.contain(
                    rgba,
                    (item.width, item.height),
                    method=Image.Resampling.LANCZOS,
                )
            else:
                frame = ImageOps.fit(
                    rgba,
                    (item.width, item.height),
                    method=Image.Resampling.LANCZOS,
                )
        if item.circle:
            mask = Image.new("L", frame.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, frame.width - 1, frame.height - 1), fill=255)
            frame.putalpha(mask)
            if item.border_width:
                frame_draw = ImageDraw.Draw(frame)
                inset = item.border_width // 2
                frame_draw.ellipse(
                    (inset, inset, frame.width - 1 - inset, frame.height - 1 - inset),
                    outline=(255, 255, 255, 112),
                    width=item.border_width,
                )
        offset = ((item.width - frame.width) // 2, (item.height - frame.height) // 2)
        background.alpha_composite(frame, (item.x + offset[0], item.y + offset[1]))
        frame.close()

    draw = ImageDraw.Draw(background)
    for item in text_layer:
        red, green, blue, alpha = ImageColor.getcolor(item.fill, "RGBA")
        alpha = round(alpha * item.opacity)
        anchor = {"start": "ls", "middle": "ms", "end": "rs"}[item.anchor]
        draw.text(
            (item.x, item.y),
            item.value,
            font=font_for_text(item.value, item.size),
            fill=(red, green, blue, alpha),
            anchor=anchor,
        )
    result = BytesIO()
    background.convert("RGB").save(result, "JPEG", quality=92)
    background.close()
    result.seek(0)
    return result


async def render_score_svg(data: dict) -> BytesIO:
    """Render a fresh card off the event loop; only static artwork is cached."""
    return await asyncio.to_thread(_render_score_svg_sync, data)
