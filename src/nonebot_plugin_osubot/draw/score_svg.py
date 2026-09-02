"""Native resvg renderer for the refined 1440x900 single-score card."""

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
from .svg_render import FONT_FAMILY, escape_text, fit_text, font_for_text, render_svg_png, truncate_text


WIDTH = 1440
HEIGHT = 900
PINK = "#ff4f96"
CYAN = "#4ce1e7"
GREEN = "#66f2a3"

_MODE_STYLES = {
    "STD": (PINK, "#e93689"),
    "OSU": (PINK, "#e93689"),
    "TAIKO": ("#38bdf8", "#0284c7"),
    "CTB": ("#10b981", "#047857"),
    "CATCH": ("#10b981", "#047857"),
    "MANIA": ("#8b5cf6", "#6d28d9"),
}


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
        background = ImageOps.fit(source.convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.BILINEAR)
    background = background.filter(ImageFilter.GaussianBlur(10))
    background = ImageEnhance.Color(background).enhance(1.3)
    background = ImageEnhance.Brightness(background).enhance(0.68)
    atmosphere = Image.frombytes("RGBA", (WIDTH, HEIGHT), _atmosphere_rgba())
    background = background.convert("RGBA")
    background.alpha_composite(atmosphere)
    atmosphere.close()
    result = BytesIO()
    flattened = background.convert("RGB")
    flattened.save(result, "JPEG", quality=72)
    flattened.close()
    background.close()
    return result.getvalue()


@lru_cache(maxsize=1)
def _atmosphere_rgba() -> bytes:
    """Pre-rasterize cover-independent ambience once per process.

    Rendering the full-canvas gradients and 4 px grain as SVG made resvg
    repaint tens of thousands of pattern tiles for every score. The result is
    static, so compose it into the per-cover background cache instead.
    """
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    shade_row = Image.new("RGBA", (WIDTH, 1))
    shade_pixels = []
    split = round(WIDTH * 0.45)
    for x in range(WIDTH):
        if x <= split:
            ratio = x / max(1, split)
            alpha = round(240 + (204 - 240) * ratio)
        else:
            ratio = (x - split) / max(1, WIDTH - 1 - split)
            alpha = round(204 + (230 - 204) * ratio)
        shade_pixels.append((6, 12, 22, alpha))
    shade_row.putdata(shade_pixels)
    shade = shade_row.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
    overlay.alpha_composite(shade)
    shade.close()
    shade_row.close()

    for colour, center, size, opacity in (
        ((255, 79, 150), (round(WIDTH * 0.80), round(HEIGHT * 0.22)), (1380, 860), 0.22),
        ((76, 225, 231), (round(WIDTH * 0.18), round(HEIGHT * 0.80)), (1296, 810), 0.18),
    ):
        radial = ImageOps.invert(Image.radial_gradient("L"))
        # Pillow's radial gradient reaches zero only in the corners. Normalize
        # it to an inscribed ellipse so a glow pasted partly off-canvas has no
        # visible rectangular edge at the midpoint of its bounds.
        radial = radial.point(lambda value: max(0, value - 80) * 255 // 175)
        radial = radial.resize(size, Image.Resampling.BILINEAR)
        radial = radial.point(lambda value, maximum=round(255 * opacity): value * maximum // 255)
        mask = Image.new("L", (WIDTH, HEIGHT), 0)
        mask.paste(radial, (center[0] - size[0] // 2, center[1] - size[1] // 2))
        glow = Image.new("RGBA", (WIDTH, HEIGHT), (*colour, 0))
        glow.putalpha(mask)
        overlay.alpha_composite(glow)
        glow.close()
        mask.close()
        radial.close()

    grain_mask = Image.new("L", (WIDTH, HEIGHT), 0)
    grain_points = [(x, y) for y in range(1, HEIGHT, 4) for x in range(1, WIDTH, 4)]
    ImageDraw.Draw(grain_mask).point(grain_points, fill=31)
    grain = Image.new("RGBA", (WIDTH, HEIGHT), (255, 255, 255, 0))
    grain.putalpha(grain_mask)
    overlay.alpha_composite(grain)
    grain.close()
    grain_mask.close()

    raw = overlay.tobytes()
    overlay.close()
    return raw


def _mode_code(data: dict) -> str:
    code = str(data.get("mode_code") or "STD").upper()
    return "CTB" if code == "CATCH" else "STD" if code == "OSU" else code


def _mode_style(data: dict) -> tuple[str, str]:
    return _MODE_STYLES.get(_mode_code(data), _MODE_STYLES["STD"])


def _mode_icon(code: str, x: float, y: float) -> str:
    if code == "MANIA":
        mark = (
            f'<circle cx="{x}" cy="{y}" r="6.5" fill="none" stroke="#fff" stroke-width="1.5"/>'
            f'<path d="M{x - 3.2} {y + 3}V{y - 2}M{x} {y + 3}V{y - 4}M{x + 3.2} {y + 3}V{y - 1}" '
            'stroke="#fff" stroke-width="1.4" stroke-linecap="round"/>'
        )
    elif code == "TAIKO":
        mark = (
            f'<circle cx="{x}" cy="{y}" r="6.5" fill="none" stroke="#fff" stroke-width="1.5"/>'
            f'<circle cx="{x}" cy="{y}" r="3.2" fill="none" stroke="#fff" stroke-width="1.4"/>'
        )
    elif code == "CTB":
        mark = (
            f'<circle cx="{x}" cy="{y}" r="6.5" fill="none" stroke="#fff" stroke-width="1.5"/>'
            f'<circle cx="{x - 2.1}" cy="{y - 2.2}" r="1.2" fill="#fff"/>'
            f'<circle cx="{x + 2.5}" cy="{y}" r="1.2" fill="#fff"/>'
            f'<circle cx="{x - 1}" cy="{y + 3}" r="1.2" fill="#fff"/>'
        )
    else:
        mark = (
            f'<circle cx="{x}" cy="{y}" r="6.5" fill="none" stroke="#fff" stroke-width="1.5"/>'
            f'<circle cx="{x}" cy="{y}" r="2.2" fill="#fff"/>'
        )
    return f'<g data-role="mode-icon">{mark}</g>'


def _render_header(data: dict) -> str:
    code = _mode_code(data)
    pill_width = max(64, round(_text_width(code, 12) + 39))
    parts = [
        f'<rect x="44" y="27" width="{pill_width}" height="26" rx="6" fill="url(#mode-accent)"/>',
        _mode_icon(code, 58, 40),
        _text(70, 45, code, 12, weight=800),
        _text(44 + pill_width + 12, 46, "单曲成绩结算", 13, fill="#94a3b8", weight=700),
        '<path d="M44 64H1396" stroke="#ffffff1f"/>',
    ]
    right = 1396
    date_label = f"达成时间: {data.get('ended_at', '')}"
    date_width = _text_width(date_label, 12)
    parts.append(_text(right, 46, date_label, 12, fill="#cbd5e1", weight=700, anchor="end"))
    status = str(data.get("status") or "").upper()
    status_width = max(66, round(_text_width(status, 11) + 18))
    status_x = right - date_width - 14 - status_width
    parts.extend(
        [
            f'<rect x="{status_x}" y="28" width="{status_width}" height="24" rx="6" '
            'fill="#ffffff14" stroke="#ffffff2e"/>',
            _text(status_x + status_width / 2, 45, status, 11, weight=800, anchor="middle"),
        ]
    )
    score_version = data.get("score_version")
    if score_version:
        badge_text = "Lazer" if score_version == "lazer" else "Stable"
        badge_colour = CYAN if score_version == "lazer" else PINK
        badge_x = status_x - 76
        parts.extend(
            [
                f'<rect x="{badge_x}" y="28" width="62" height="24" rx="6" fill="{badge_colour}" '
                f'fill-opacity=".14" stroke="{badge_colour}" stroke-opacity=".4"/>',
                f'<circle cx="{badge_x + 10}" cy="40" r="2.5" fill="{badge_colour}"/>',
                _text(badge_x + 18, 45, badge_text, 11, fill=badge_colour, weight=800),
            ]
        )
    return "".join(parts)


def _render_map_strip(data: dict) -> str:
    info_x = 368
    title = str(data.get("title") or "")
    artist = str(data.get("artist") or "")
    version = str(data.get("version") or "")
    stars = str(data.get("stars") or "0")
    star_label = f"★ {stars}"
    star_width = max(78, round(_text_width(star_label, 16) + 26))
    star_colour = _star_colour(stars)
    try:
        star_text_colour = "#101925" if float(stars) < 6.5 else "#ffd966"
    except ValueError:
        star_text_colour = "#ffd966"

    mod_items = [item for item in list(data.get("mods") or []) if str(item.get("name") or "").upper() != "NM"][:8]
    mod_names = [str(item.get("name") or "") for item in mod_items]
    speed_changes = {
        name: str(item["speed_change"]) for name, item in zip(mod_names, mod_items) if item.get("speed_change")
    }
    estimated_mod_width = sum(51 + (63 if item.get("speed_change") else 0) for item in mod_items)
    reserved = star_width + 12 + (estimated_mod_width + 12 if mod_items else 0)
    title_max = max(190, min(440, 1030 - info_x - reserved))
    title_size = fit_text(title, title_max, 46, 24)
    title = truncate_text(title, title_max, title_size)
    title_width = _text_width(title, title_size)
    star_x = round(info_x + title_width + 12)
    mods_x = star_x + star_width + 12
    mods_svg = mod_strip(
        mod_names,
        speed_changes,
        x=mods_x,
        y=122,
        icon_size=36,
        max_width=max(0, 1030 - mods_x),
        preserve_artwork_ratio=True,
        text_renderer=_text,
    )

    accent, _accent_dark = _mode_style(data)
    artist_size = fit_text(artist, 285, 17, 12)
    artist = truncate_text(artist, 285, artist_size)
    artist_width = _text_width(artist, artist_size)
    version_width = max(76, min(280, round(_text_width(version, 14) + 22)))
    version = truncate_text(version, version_width - 22, 14)
    version_x = round(info_x + artist_width + 28)
    map_id_x = version_x + version_width + 28
    quick_items = [
        ("速度", f"{data.get('bpm', '--')} BPM"),
        ("物件", str(data.get("objects", "--"))),
    ]
    if _mode_code(data) == "MANIA":
        keys = next(
            (item.get("current") for item in data.get("dimensions", []) if item.get("name") == "KEYS"),
            None,
        )
        quick_items.append(("键位", f"{keys}K" if keys else str(data.get("length", "--"))))
        if data.get("ln_ratio") is not None:
            quick_items.append(("LN占比", str(data["ln_ratio"])))
    else:
        quick_items.append(("时长", str(data.get("length", "--"))))

    parts = [
        '<rect x="50" y="88" width="300" height="180" rx="15" fill="#00000073"/>',
        '<rect x="44" y="80" width="300" height="180" rx="15" fill="#111925"/>',
        _image(data.get("cover"), 44, 80, 300, 180, clip="map-cover"),
        '<rect x="44.5" y="80.5" width="299" height="179" rx="14.5" fill="none" stroke="#ffffff32"/>',
        _text(info_x, 151, title, title_size, weight=700),
        f'<rect x="{star_x}" y="122" width="{star_width}" height="32" rx="16" '
        f'fill="{star_colour}" stroke="#ffffff33"/>',
        _text(
            star_x + star_width / 2,
            145,
            star_label,
            16,
            fill=star_text_colour,
            weight=700,
            anchor="middle",
        ),
        mods_svg,
        _text(info_x, 186, artist, artist_size, fill="#cbd5e1", weight=700),
        _text(version_x - 16, 186, "•", 14, fill="#cbd5e1", anchor="middle"),
        f'<rect x="{version_x}" y="164" width="{version_width}" height="26" rx="7" '
        f'fill="{accent}" fill-opacity=".14" stroke="{accent}" stroke-opacity=".7"/>',
        _text(version_x + version_width / 2, 183, version, 14, fill=accent, weight=700, anchor="middle"),
        _text(map_id_x - 16, 186, "•", 14, fill="#cbd5e1", anchor="middle"),
        _text(map_id_x, 186, f"ID: {data.get('map_id', '')}", 15, fill="#94a3b8", weight=700),
    ]
    cursor = info_x
    for label, value in quick_items:
        prefix = f"{label}: "
        parts.append(_text(cursor, 219, prefix, 14, fill="#94a3b8", weight=700))
        value_x = cursor + _text_width(prefix, 14)
        parts.append(_text(value_x, 219, value, 14, fill="#f1f5f9", weight=700))
        cursor = value_x + _text_width(value, 14) + 30
    return "".join(parts)


def _render_hero_metrics(data: dict) -> str:
    score = str(data.get("score") or "0")
    score_size = fit_text(score, 900, 68, 46)
    pp_value = str(data.get("pp") or "0")
    pp_width = _text_width(pp_value, 34)
    combo = str(data.get("combo") or "0x")
    combo_is_full = bool(data.get("combo_is_full"))
    combo_display = combo[:-1] if combo_is_full and combo.endswith("x") else combo
    combo_colour = GREEN if combo_is_full else "#ffffff"
    parts = [
        _text(44, 318, "最终得分", 13, fill="#94a3b8", weight=700),
        _text(44, 409, score, score_size, weight=800),
        '<path d="M44 493H980" stroke="#ffffff1f"/>',
        _text(44, 522, "本次表现", 12, fill="#94a3b8", weight=700),
        _text(44, 559, pp_value, 34, fill=CYAN, weight=700),
        _text(48 + pp_width, 559, "pp", 16, fill=PINK, weight=700),
        _text(210, 522, "准确率", 12, fill="#94a3b8", weight=700),
        _text(210, 559, f"{data.get('accuracy', '0')}%", 34, weight=700),
        _text(405, 522, "最大连击", 12, fill="#94a3b8", weight=700),
        _text(405, 559, combo_display, 34, fill=combo_colour, weight=700),
    ]
    if combo_is_full:
        marker_x = 405 + _text_width(combo_display, 34) + 10
        parts.append(_text(marker_x, 558, "★ PERFECT", 16, fill=GREEN, weight=700))
    return "".join(parts)


def _render_identity(data: dict) -> str:
    left = 68
    owners = list(data.get("owners") or [])[:20]
    owner_count = len(owners)
    heading = "玩家 & 合作谱师" if owner_count > 1 else "玩家 & 谱师"
    username = str(data.get("username") or "")
    team = data.get("team") or {}
    if team:
        player_meta = f"[{team.get('short_name', '')}] {team.get('name', '')}"
    else:
        ranks = []
        if data.get("global_rank"):
            ranks.append(f"全球 #{data['global_rank']}")
        if data.get("country_rank"):
            ranks.append(f"{data.get('country', '')} #{data['country_rank']}")
        player_meta = " · ".join(ranks) or f"UID {data.get('user_id', '')}"
    player_meta = truncate_text(player_meta, 244, 13)
    stat_bits = []
    if data.get("global_rank"):
        stat_bits.append(f"全球排名: #{data['global_rank']}")
    if data.get("country_rank"):
        stat_bits.append(f"地区: {data.get('country', '')} #{data['country_rank']}")
    third = str(data.get("profile_third_value") or "")
    if third and third != "—":
        stat_bits.append(third)
    stat_line = "  ·  ".join(stat_bits) or f"UID {data.get('user_id', '')}"
    parts = [
        _text(left, 655, heading, 15, fill="#94a3b8", weight=700),
        _queue_pillow_image(data.get("avatar"), left, 669, 44, 44, circle=True, border_width=2),
        _text(left + 56, 687, username, fit_text(username, 210, 19, 13), weight=700),
        _text(left + 56, 708, player_meta, 13, fill="#94a3b8"),
        '<path d="M68 728H368" stroke="#ffffff1a"/>',
        _text(left, 752, stat_line, fit_text(stat_line, 298, 13, 10), fill="#94a3b8", weight=700),
    ]
    if not owners:
        return "".join(parts)

    section_top = 785 if owner_count <= 2 else 743 if owner_count <= 8 else 780
    if owner_count == 1:
        title = "谱面谱师"
    elif owner_count <= 8:
        title = f"合作谱师 · {owner_count} 人"
    else:
        title = f"合作谱师 · {owner_count} 人合作谱面"
    parts.extend(
        [
            f'<path d="M68 {section_top}H368" stroke="#ffffff1a"/>',
            _text(left, section_top + 21, title, 12, fill=CYAN, weight=700),
        ]
    )
    if owner_count == 1:
        owner = owners[0]
        parts.extend(
            [
                _queue_pillow_image(
                    owner.get("avatar"),
                    left,
                    section_top + 29,
                    28,
                    28,
                    circle=True,
                    border_width=1,
                ),
                _text(left + 38, section_top + 50, owner.get("username", ""), 15, weight=700),
            ]
        )
    elif owner_count <= 8:
        for index, owner in enumerate(owners):
            column = index % 2
            row = index // 2
            x = left + column * 150
            y = section_top + 29 + row * 25
            name = str(owner.get("username") or "")
            parts.extend(
                [
                    _queue_pillow_image(owner.get("avatar"), x, y, 22, 22, circle=True, border_width=1),
                    _text(x + 30, y + 17, name, fit_text(name, 112, 13, 9), fill="#e2e8f0"),
                ]
            )
    else:
        for index, owner in enumerate(owners):
            column = index % 10
            row = index // 10
            x = left + 2 + column * 24 + (12 if row else 0)
            y = section_top + 29 + row * 27
            parts.append(_queue_pillow_image(owner.get("avatar"), x, y, 26, 26, circle=True, border_width=2))
    return "".join(parts)


def _judgement_colours(data: dict, count: int) -> list[str]:
    code = _mode_code(data)
    if code == "MANIA":
        colours = ["#00f0ff", "#fbbf24", "#10b981", "#38bdf8", "#94a3b8", PINK]
    elif code == "TAIKO":
        colours = ["#38bdf8", "#fbbf24", PINK]
    elif code == "CTB":
        colours = ["#10b981", "#38bdf8", "#fbbf24", PINK]
    else:
        colours = [CYAN, "#10b981", "#fbbf24", PINK]
    return [colours[index % len(colours)] for index in range(count)]


def _render_judgements(data: dict) -> str:
    left = 408
    width = 330
    parts = [_text(left, 655, "判定明细", 15, fill="#94a3b8", weight=700)]
    ratio = str(data.get("ratio") or "")
    if ratio:
        parts.append(
            f'<g data-role="mania-ratio">'
            f"{_text(left + width, 654, f'黄彩比 {ratio}', 12, fill='#fbbf24', weight=700, anchor='end')}"
            "</g>"
        )
    judgements = list(data.get("judgements") or [])
    count = len(judgements)
    if not count:
        return "".join(parts)
    colours = _judgement_colours(data, count)
    if count == 3:
        columns, gap_x, gap_y = 1, 0, 8
    elif count == 6:
        columns, gap_x, gap_y = 3, 8, 8
    else:
        columns, gap_x, gap_y = 2, 10, 10
    rows = (count + columns - 1) // columns
    cell_width = (width - gap_x * (columns - 1)) / columns
    cell_height = (188 - gap_y * (rows - 1)) / rows
    for index, (item, colour) in enumerate(zip(judgements, colours)):
        column = index % columns
        row = index // columns
        x = left + column * (cell_width + gap_x)
        y = 668 + row * (cell_height + gap_y)
        opacity = 1 if item.get("value") else 0.45
        parts.extend(
            [
                f'<rect x="{x}" y="{y}" width="{cell_width}" height="{cell_height}" rx="10" '
                f'fill="#ffffff" fill-opacity="{0.05 * opacity}"/>',
                f'<path d="M{x + 5} {y + 5}V{y + cell_height - 5}" stroke="{colour}" stroke-width="5" '
                f'stroke-linecap="round" opacity="{opacity}"/>',
            ]
        )
        if columns == 1:
            parts.extend(
                [
                    _text(
                        x + 20,
                        y + cell_height / 2 + 6,
                        item.get("label", ""),
                        16,
                        fill="#94a3b8",
                        weight=700,
                        opacity=opacity,
                    ),
                    _text(
                        x + cell_width - 16,
                        y + cell_height / 2 + 8,
                        item.get("display", "0"),
                        24,
                        weight=700,
                        anchor="end",
                        opacity=opacity,
                    ),
                ]
            )
        else:
            parts.extend(
                [
                    _text(
                        x + 18,
                        y + cell_height * 0.43,
                        item.get("label", ""),
                        13 if columns == 3 else 14,
                        fill="#94a3b8",
                        weight=700,
                        opacity=opacity,
                    ),
                    _text(
                        x + 18,
                        y + cell_height * 0.78,
                        item.get("display", "0"),
                        22 if columns == 3 else 26,
                        weight=700,
                        opacity=opacity,
                    ),
                ]
            )
    return "".join(parts)


def _render_dimensions(data: dict) -> str:
    left = 778
    right = 1038
    parts = [
        _text(left, 655, "谱面参数", 15, fill="#94a3b8", weight=700),
        _text(
            right,
            654,
            f"0 – {data.get('dimension_max', 10)}",
            11,
            fill="#94a3b8",
            weight=700,
            anchor="end",
        ),
    ]
    dimensions = list(data.get("dimensions") or [])
    for index, item in enumerate(dimensions):
        center_y = 668 + 188 * (index + 0.5) / len(dimensions)
        track_x = left + 51
        track_width = 145
        fill_width = track_width * float(item.get("current_pos") or 0) / 100
        changed = bool(item.get("changed"))
        colour = PINK if changed else CYAN
        current = str(item.get("current", ""))
        if item.get("name") == "KEYS":
            current = f"{current}K"
        parts.extend(
            [
                _text(left, center_y + 5, item.get("name", ""), 15, fill="#cbd5e1", weight=700),
                f'<rect x="{track_x}" y="{center_y - 4}" width="{track_width}" height="8" rx="4" fill="#ffffff1f"/>',
                f'<rect x="{track_x}" y="{center_y - 4}" width="{fill_width}" height="8" rx="4" fill="{colour}"/>',
                _text(
                    right,
                    center_y + 6,
                    current,
                    18,
                    fill=PINK if changed else "#ffffff",
                    weight=700,
                    anchor="end",
                ),
            ]
        )
    return "".join(parts)


def _projection_label(label: object) -> str:
    labels = {
        "96% ACC": "96% 准确率",
        "98% ACC": "98% 准确率",
        "IF FC": "无失误推演 (IF FC)",
        "SS PP": "全准理论上限 (SS)",
    }
    return labels.get(str(label).upper(), str(label))


def _render_pp(data: dict) -> str:
    left = 1078
    width = 294
    parts = [_text(left, 655, "表现推演", 15, fill="#94a3b8", weight=700)]
    targets = list(data.get("pp_targets") or data.get("pp_items") or [])
    if not targets:
        return "".join(parts)
    card_height = min(42, (188 - 6 * (len(targets) - 1)) / len(targets))
    gap = (188 - card_height * len(targets)) / max(1, len(targets) - 1) if len(targets) > 1 else 0
    for index, item in enumerate(targets):
        y = 668 + index * (card_height + gap)
        label = _projection_label(item.get("label", ""))
        is_ss = "SS" in str(item.get("label", "")).upper()
        stroke = PINK if is_ss else "none"
        parts.extend(
            [
                f'<rect x="{left}" y="{y}" width="{width}" height="{card_height}" rx="8" '
                f'fill="{PINK if is_ss else "#ffffff"}" fill-opacity="{0.18 if is_ss else 0.05}" '
                f'stroke="{stroke}" stroke-opacity=".45"/>',
                _text(
                    left + 12,
                    y + card_height / 2 + 5,
                    label,
                    13,
                    fill="#ff7184" if is_ss else "#94a3b8",
                    weight=700,
                ),
                _text(
                    left + width - 12,
                    y + card_height / 2 + 6,
                    f"{item.get('value', '0')} pp",
                    18 if is_ss else 17,
                    fill=PINK if is_ss else "#ffffff",
                    weight=700,
                    anchor="end",
                ),
            ]
        )
    return "".join(parts)


def build_score_svg(data: dict) -> str:
    accent, accent_dark = _mode_style(data)
    identity_svg = _render_identity(data)
    judgements_svg = _render_judgements(data)
    dimensions_svg = _render_dimensions(data)
    pp_svg = _render_pp(data)
    rank_image = _queue_pillow_image(data.get("rank_image"), 1046, 168, 320, 340, contain=True)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <clipPath id="canvas"><rect width="1440" height="900" rx="20"/></clipPath>
  <clipPath id="map-cover"><rect x="44" y="80" width="300" height="180" rx="15"/></clipPath>
  <linearGradient id="mode-accent" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{accent}"/><stop offset="1" stop-color="{accent_dark}"/></linearGradient>
  <radialGradient id="rank-glow"><stop stop-color="#ff4f96" stop-opacity=".18"/><stop offset=".68" stop-color="#ff4f96" stop-opacity="0"/></radialGradient>
</defs>
<g clip-path="url(#canvas)">
  {_render_header(data)}
  {_render_map_strip(data)}
  {_render_hero_metrics(data)}
  <ellipse cx="1206" cy="333" rx="175" ry="175" fill="url(#rank-glow)"/>
  {rank_image}
  <rect x="44" y="618" width="1352" height="256" rx="18" fill="#0a121e" fill-opacity=".88" stroke="#ffffff24"/>
  <path d="M388 636V856M758 636V856M1058 636V856" stroke="#ffffff1a"/>
  {identity_svg}
  {judgements_svg}
  {dimensions_svg}
  {pp_svg}
  <rect x=".5" y=".5" width="1439" height="899" rx="19.5" fill="none" stroke="#ffffff1a"/>
</g>
</svg>"""


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

    with Image.open(BytesIO(_background_jpeg(str(data["cover"])))) as cached_background:
        card = cached_background.convert("RGBA")
    background = Image.new("RGBA", (WIDTH, HEIGHT), (4, 7, 13, 255))
    rounded_mask = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(rounded_mask).rounded_rectangle((0, 0, WIDTH - 1, HEIGHT - 1), radius=20, fill=255)
    background.paste(card, (0, 0), rounded_mask)
    card.close()
    rounded_mask.close()
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
            mask.close()
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
    flattened = background.convert("RGB")
    flattened.save(result, "JPEG", quality=92)
    flattened.close()
    background.close()
    result.seek(0)
    return result


async def render_score_svg(data: dict) -> BytesIO:
    """Render one refined score card off the event loop through resvg."""
    return await asyncio.to_thread(_render_score_svg_sync, data)
