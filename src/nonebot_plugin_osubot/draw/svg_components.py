"""Reusable SVG fragments for native fixed-layout cards."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .svg_render import FONT_FAMILY, escape_text, file_data_uri, truncate_text


MOD_PATH = Path(__file__).parent.parent / "osufile" / "mods"
STAR_STOPS = (
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

_DOUBLE_S_PATH = (
    "M5.3393 10.4417V12.0801H13.0065C15.4769 12.0801 16.4241 11.0305 16.4241 9.54568"
    "C16.4241 7.77928 15.0929 7.12648 13.0321 6.96008L9.0001 6.64008C7.5665 6.52488 7.2337 6.26888 7.2337 5.78248"
    "C7.2337 5.19368 7.7201 4.96328 8.5777 4.96328H15.8609V3.32488H8.7441C6.9393 3.32488 5.3777 3.97768 5.3777 5.83368"
    "C5.3777 7.44648 6.5553 8.15048 8.5265 8.30408L12.7633 8.63688C14.0177 8.73928 14.5425 9.03368 14.5425 9.62248"
    "C14.5425 10.1089 14.1969 10.4417 13.1217 10.4417H5.3393Z"
    "M15.7568 10.4417V12.0801H23.424C25.8944 12.0801 26.8416 11.0305 26.8416 9.54568"
    "C26.8416 7.77928 25.5104 7.12648 23.4496 6.96008L19.4176 6.64008C17.984 6.52488 17.6512 6.26888 17.6512 5.78248"
    "C17.6512 5.19368 18.1376 4.96328 18.9952 4.96328H26.2784V3.32488H19.1616C17.3568 3.32488 15.7952 3.97768 15.7952 5.83368"
    "C15.7952 7.44648 16.9728 8.15048 18.944 8.30408L23.1808 8.63688C24.4352 8.73928 24.96 9.03368 24.96 9.62248"
    "C24.96 10.1089 24.6144 10.4417 23.5392 10.4417H15.7568Z"
)
_S_PATH = (
    "M10.548 10.4417V12.0801H18.2153C20.6857 12.0801 21.6329 11.0305 21.6329 9.54568"
    "C21.6329 7.77928 20.3017 7.12648 18.2409 6.96008L14.2088 6.64008C12.7752 6.52488 12.4424 6.26888 12.4424 5.78248"
    "C12.4424 5.19368 12.9288 4.96328 13.7864 4.96328H21.0697V3.32488H13.9528C12.148 3.32488 10.5864 3.97768 10.5864 5.83368"
    "C10.5864 7.44648 11.764 8.15048 13.7352 8.30408L17.9721 8.63688C19.2265 8.73928 19.7513 9.03368 19.7513 9.62248"
    "C19.7513 10.1089 19.4057 10.4417 18.3305 10.4417H10.548Z"
)
_A_PATH = (
    "M18.5418 5.49208C18.0138 4.47208 17.4018 3.75208 15.9978 3.75208C14.5938 3.75208 13.9698 4.47208 13.4538 5.49208"
    "L10.0938 12.0801H11.9298L12.9738 10.0521H19.0218L20.0658 12.0801H21.9138L18.5418 5.49208Z"
    "M18.2298 8.52808H13.7538L15.1458 5.84008C15.3258 5.49208 15.5538 5.27608 15.9978 5.27608"
    "C16.4418 5.27608 16.6698 5.49208 16.8498 5.84008L18.2298 8.52808Z"
)


def text(
    x: float,
    y: float,
    value: object,
    size: int,
    *,
    fill: str = "#ffffff",
    anchor: str = "start",
    weight: int = 400,
    opacity: float = 1,
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT_FAMILY}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill}" opacity="{opacity}">'
        f"{escape_text(value)}</text>"
    )


def fitted_text(
    x: float,
    y: float,
    value: object,
    size: int,
    max_width: float,
    **kwargs,
) -> str:
    return text(x, y, truncate_text(value, max_width, size), size, **kwargs)


def gradient_text(
    x: float,
    y: float,
    value: object,
    size: int,
    start: str,
    end: str,
    *,
    anchor: str = "start",
    weight: int = 400,
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT_FAMILY}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}" fill="{start}" data-gradient-start="{start}" data-gradient-end="{end}">'
        f"{escape_text(value)}</text>"
    )


def rank_seal(rank: str, x: float, y: float, *, width: float = 60, height: float = 30) -> str:
    """Render the compact osu! rank seal used by info cards."""
    key = rank.upper()
    if key not in {"XH", "X", "SH", "S", "A"}:
        key = "A"
    pink = key in {"XH", "X"}
    silver = key in {"XH", "SH"}
    path = _DOUBLE_S_PATH if pink else _S_PATH if key != "A" else _A_PATH
    base = "#CE1C9D" if pink else "#00A8B5" if key != "A" else "#7CCE14"
    light = "#DE31AE" if pink else "#02B5C3" if key != "A" else "#88DA20"
    dark = "#C30B90" if pink else "#009DAA" if key != "A" else "#72C904"
    darkest = "#BE0089" if pink else "#0096A2" if key != "A" else "#69BB00"
    shadow = "#5E244E" if pink else "#095056"
    suffix = f"{key.lower()}-{round(x * 10)}-{round(y * 10)}-{round(width * 10)}"
    clip_id = f"rank-clip-{suffix}"
    gradient_id = f"rank-gradient-{suffix}"
    foreground = "#275227" if key == "A" else f"url(#{gradient_id})"
    gradient = ""
    shadow_path = ""
    if key != "A":
        top, bottom = ("#ffffff", "#AADFF0") if silver else ("#FFE7A8", "#FFB800")
        gradient = f'<linearGradient id="{gradient_id}" x1="16" y1="2" x2="16" y2="16" gradientUnits="userSpaceOnUse"><stop stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>'
        shadow_path = f'<path d="{path}" transform="translate(0 1)" fill="{shadow}" opacity=".5"/>'
    return f"""<svg x="{x}" y="{y}" width="{width}" height="{height}" viewBox="0 0 32 16"><defs><clipPath id="{clip_id}"><rect width="32" height="16" rx="8"/></clipPath>{gradient}</defs><g clip-path="url(#{clip_id})"><rect width="32" height="16" rx="8" fill="{base}"/><path d="M16 -9L33.3205 21H-1.32051Z" fill="{light}"/><path d="M27.5 3L33.9952 14.25H21.0048Z" fill="{dark}"/><path d="M7.5 -2L11.3971 4.75H3.60289Z M9.5 13L13.3971 19.75H5.60289Z" fill="{darkest}"/>{shadow_path}<path d="{path}" fill="{foreground}"/></g></svg>"""


def image(
    uri: str | None,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    clip: str | None = None,
    contain: bool = False,
) -> str:
    if not uri:
        return ""
    clip_attr = f' clip-path="url(#{escape_text(clip)})"' if clip else ""
    aspect = "xMidYMid meet" if contain else "xMidYMid slice"
    return (
        f'<image href="{escape_text(uri)}" x="{x}" y="{y}" width="{width}" height="{height}" '
        f'preserveAspectRatio="{aspect}"{clip_attr}/>'
    )


def star_color(value: float) -> str:
    if value < 0.1:
        return "#aaaaaa"
    if value >= 9:
        return "#000000"
    for (left, left_color), (right, right_color) in zip(STAR_STOPS, STAR_STOPS[1:]):
        if value <= right:
            ratio = max(0.0, min(1.0, (value - left) / (right - left)))
            first = tuple(int(left_color[index : index + 2], 16) for index in (1, 3, 5))
            second = tuple(int(right_color[index : index + 2], 16) for index in (1, 3, 5))
            mixed = tuple(round(a * (1 - ratio) + b * ratio) for a, b in zip(first, second))
            return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"
    return "#000000"


def supporter_badge(x: float, y: float, level: int, *, height: float = 23) -> str:
    if level <= 0:
        return ""
    level = min(level, 5)
    step = height * 0.35
    width = height * 0.72 + step * level
    parts = [f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{height / 2}" fill="#ed438e"/>']
    heart_size = height * 0.42
    for index in range(level):
        left = x + height * 0.29 + index * step
        top = y + height * 0.31
        parts.append(
            f'<path d="M{left + heart_size / 2} {top + heart_size}'
            f"C{left + heart_size * 0.42} {top + heart_size * 0.91} {left} {top + heart_size * 0.64} {left} {top + heart_size * 0.33}"
            f"C{left} {top + heart_size * 0.1} {left + heart_size * 0.16} {top} {left + heart_size * 0.32} {top}"
            f"C{left + heart_size * 0.44} {top} {left + heart_size / 2} {top + heart_size * 0.09} {left + heart_size / 2} {top + heart_size * 0.17}"
            f"C{left + heart_size / 2} {top + heart_size * 0.09} {left + heart_size * 0.58} {top} {left + heart_size * 0.7} {top}"
            f"C{left + heart_size * 0.86} {top} {left + heart_size} {top + heart_size * 0.1} {left + heart_size} {top + heart_size * 0.33}"
            f"C{left + heart_size} {top + heart_size * 0.64} {left + heart_size * 0.58} {top + heart_size * 0.91} "
            f'{left + heart_size / 2} {top + heart_size}Z" fill="#fff"/>'
        )
    return "".join(parts)


def mod_strip(
    mods: list[str],
    speed_changes: dict[str, str],
    *,
    x: float,
    y: float,
    icon_size: float,
    max_width: float,
    item_gap: float | None = None,
    preserve_artwork_ratio: bool = True,
    text_renderer: Callable[..., str] = text,
) -> str:
    mods = [acronym for acronym in mods if acronym.upper() != "NM"]
    if not mods:
        return ""
    parts: list[str] = []
    cursor = x
    # Bundled mod artwork uses a 45:32 canvas. Preserve that ratio so the
    # hexagonal marks are not squeezed into or cropped by a square viewport.
    icon_width = icon_size * 45 / 32 if preserve_artwork_ratio else icon_size
    for acronym in mods:
        rate = speed_changes.get(acronym)
        extension = icon_size * 1.75 if rate else 0
        item_width = icon_width + extension
        if cursor + item_width > x + max_width:
            break
        if rate:
            backplate_left = cursor + icon_width * 0.44
            backplate_top = y
            backplate_bottom = y + icon_size
            backplate_middle = y + icon_size / 2
            # The source mod hexagon advances 8 px horizontally over half of
            # its 32 px height. Reuse that 1:2 slope for the speed badge so
            # its right edges stay parallel with the adjacent mod artwork.
            backplate_shoulder = cursor + item_width - icon_size * 0.25
            backplate_right = cursor + item_width
            parts.append(
                f'<path d="M{backplate_left},{backplate_top} H{backplate_shoulder} '
                f"L{backplate_right},{backplate_middle} L{backplate_shoulder},{backplate_bottom} "
                f'H{backplate_left} Z" fill="#431b1b" stroke="#431b1b" stroke-width="1" stroke-linejoin="round"/>'
            )
        path = MOD_PATH / f"{acronym}.png"
        if path.exists():
            parts.append(image(file_data_uri(path), cursor, y, icon_width, icon_size, contain=True))
        else:
            parts.append(text_renderer(cursor + icon_width / 2, y + icon_size * 0.67, acronym, 9, anchor="middle"))
        if rate:
            badge_size = icon_size * 0.38
            badge_x = cursor + icon_width * 0.82
            badge_y = y + icon_size * 0.07
            tooth_width = badge_size * 0.16
            tooth_height = badge_size * 0.28
            teeth = "".join(
                f'<rect x="{-tooth_width / 2}" y="{-badge_size * 0.43}" width="{tooth_width}" '
                f'height="{tooth_height}" rx="{tooth_width * 0.25}" transform="rotate({angle})"/>'
                for angle in range(0, 360, 45)
            )
            parts.append(
                f'<g data-role="mod-settings" transform="translate({badge_x} {badge_y})">'
                f'<circle r="{badge_size / 2}" fill="#6b2528"/><g fill="#ff6670">{teeth}'
                f'<circle r="{badge_size * 0.25}"/><circle r="{badge_size * 0.1}" fill="#6b2528"/></g></g>'
            )
            parts.append(
                text_renderer(
                    cursor + icon_width + extension / 2,
                    y + icon_size * 0.64,
                    rate,
                    max(8, round(icon_size * 0.32)),
                    fill="#ff7184",
                    anchor="middle",
                    weight=700,
                )
            )
        cursor += item_width + item_gap if item_gap is not None else item_width
    return "".join(parts)


def number(value: object, digits: int = 0) -> str:
    try:
        return f"{float(value or 0):,.{digits}f}"
    except (TypeError, ValueError):
        return "0"
