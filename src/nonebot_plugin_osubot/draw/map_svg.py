"""Native SVG renderers for beatmap and beatmapset information cards."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from .svg_components import STAR_STOPS, fitted_text, image, mod_strip, number, star_color, text
from .svg_render import escape_text, render_svg_jpeg_async, text_width


WIDTH = 1400
PINK = "#ff4d96"
CYAN = "#43d5df"
PANEL = "#101b28"
MODE_NAMES = ("STANDARD", "TAIKO", "CATCH", "MANIA")
MODE_GLYPHS = ("\ue800", "\ue803", "\ue801", "\ue802")
STATUS_NAMES = {
    "ranked": "已上架",
    "approved": "已批准",
    "loved": "社区喜爱",
    "qualified": "已过审",
    "pending": "待定",
    "graveyard": "坟场",
    "wip": "制作中",
}


def _cover_use(
    prefix: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    clip: str | None = None,
) -> str:
    scale = max(width / WIDTH, height / 900)
    render_width, render_height = WIDTH * scale, 900 * scale
    offset_x = x + (width - render_width) / 2
    offset_y = y + (height - render_height) / 2
    use = f'<use href="#{prefix}-cover-source" transform="translate({offset_x} {offset_y}) scale({scale})"/>'
    return f'<g clip-path="url(#{clip})">{use}</g>' if clip else use


def _background(cover: str | None, height: int, prefix: str, *, external_canvas: bool = False) -> str:
    left_width, left_height = (580, 420) if prefix == "map" else (404, 314)
    cover_source = (
        f'<image id="{prefix}-cover-source" href="{escape_text(cover)}" x="0" y="0" width="{WIDTH}" height="900" preserveAspectRatio="xMidYMid slice"/>'
        if cover
        else ""
    )
    cover_layer = _cover_use(prefix, 0, 0, WIDTH, height) if cover and not external_canvas else ""
    return f"""
<defs>{cover_source}<clipPath id="{prefix}-left"><rect x="17" y="61" width="{left_width}" height="{left_height}" rx="23"/></clipPath><linearGradient id="{prefix}-shade" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#050f19" stop-opacity=".92"/><stop offset=".58" stop-color="#08121d" stop-opacity=".8"/><stop offset="1" stop-color="#141527" stop-opacity=".84"/></linearGradient><pattern id="{prefix}-texture" width="4" height="4" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".65" fill="#fff" opacity=".06"/></pattern></defs>
{cover_layer}<rect width="{WIDTH}" height="{height}" fill="url(#{prefix}-shade)"/><rect width="{WIDTH}" height="{height}" fill="url(#{prefix}-texture)"/>
<rect width="{WIDTH}" height="44" fill="#040d16aa"/><line y1="44" x2="{WIDTH}" y2="44" stroke="#ffffff22"/>
"""


def _panel(x: float, y: float, width: float, height: float, *, radius: float = 18) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="#08141fc9" stroke="#ffffff22"/>'
    )


def _left_identity(payload: dict, *, map_card: bool, card_height: int | None = None) -> str:
    beatmapset = payload["set"]
    cover_height = 420 if map_card else 314
    left_width = 580 if map_card else 404
    x = 17
    cover_y = 61
    avatar_x = 41
    creator_y = cover_y + cover_height + 28
    title = beatmapset.get("title_unicode") or beatmapset["title"]
    artist = beatmapset.get("artist_unicode") or beatmapset["artist"]
    status = STATUS_NAMES.get(str(beatmapset.get("status") or "").lower(), str(beatmapset.get("status") or ""))
    if map_card:
        badge = f'<rect x="{x + 18}" y="{cover_y + 16}" width="86" height="28" rx="0" fill="#06101bd8"/><rect x="{x + 18}" y="{cover_y + 16}" width="3" height="28" fill="{CYAN}"/>{text(x + 61, cover_y + 35, status, 11, anchor="middle", weight=700)}'
        star = float(payload["map"]["stars"])
        badge += f'<rect x="{x + left_width - 105}" y="{cover_y + 16}" width="78" height="29" rx="15" fill="{star_color(star)}" stroke="#ffffff55"/>{text(x + left_width - 66, cover_y + 36, "★ " + number(star, 2), 13, fill="#101925" if star < 6.5 else "#ffd966", anchor="middle", weight=700)}'
        note = f"来源 · {beatmapset.get('source')}" if beatmapset.get("source") else ""
    else:
        difficulties = payload["difficulties"][:20]
        minimum, maximum = float(difficulties[0]["stars"]), float(difficulties[-1]["stars"])
        badge = f'<rect x="{x + 18}" y="{cover_y + 18}" width="86" height="28" fill="#06101bd8"/><rect x="{x + 18}" y="{cover_y + 18}" width="3" height="28" fill="{CYAN}"/>{text(x + 61, cover_y + 37, status, 11, anchor="middle", weight=700)}'
        badge += text(x + left_width - 22, cover_y + 30, "难度范围", 9, anchor="end") + text(
            x + left_width - 22, cover_y + 54, f"{minimum:.2f}–{maximum:.2f}★", 17, anchor="end", weight=700
        )
        note = ""
    creator_right = x + left_width - 24
    prefix = "map" if map_card else "bmap"
    return f"""
<rect x="{x}" y="{cover_y}" width="{left_width}" height="{card_height or (782 if map_card else 822)}" rx="23" fill="#0a1520" stroke="#ffffff24"/>
{_cover_use(prefix, x, cover_y, left_width, cover_height, clip=f"{prefix}-left") if beatmapset.get("cover") else ""}
<rect x="{x}" y="{cover_y}" width="{left_width}" height="{cover_height}" fill="url(#left-cover-shade)" clip-path="url(#{prefix}-left)"/>
{badge}
{fitted_text(x + 24, cover_y + cover_height - 66, title, 43 if map_card else 36, left_width - 48, weight=700)}
{fitted_text(x + 24, cover_y + cover_height - 34, "by " + artist, 17, left_width - 48, fill="#dde5ea")}
{text(x + 24, cover_y + cover_height - 13, note, 9, fill="#ffffffcc") if note else ""}
<defs><clipPath id="{prefix}-creator"><circle cx="{avatar_x + 23}" cy="{creator_y + 23}" r="23"/></clipPath><linearGradient id="left-cover-shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05101a" stop-opacity=".25"/><stop offset="1" stop-color="#07101b" stop-opacity=".9"/></linearGradient></defs>
<circle cx="{avatar_x + 23}" cy="{creator_y + 23}" r="27" fill="#43d5df22"/><circle cx="{avatar_x + 23}" cy="{creator_y + 23}" r="24" fill="#152430" stroke="{CYAN}" stroke-width="2"/>{image(beatmapset.get("avatar"), avatar_x, creator_y, 46, 46, clip=prefix + "-creator")}
{text(99, creator_y + 15, "谱面作者", 10, fill="#ffffffbb")}{fitted_text(99, creator_y + 38, beatmapset["creator"], 18, 235 if map_card else 150, weight=700)}
{text(creator_right, creator_y + 15, "上架时间" if map_card else "来源", 10, fill="#ffffffbb", anchor="end")}{fitted_text(creator_right, creator_y + 38, beatmapset.get("ranked_date") if map_card else beatmapset.get("source") or "原创曲目", 14, 170, anchor="end")}
<line x1="{x + 20}" y1="{creator_y + 62}" x2="{x + left_width - 20}" y2="{creator_y + 62}" stroke="#ffffff22"/>
"""


def _metric(x: float, y: float, label: str, value: str, *, color: str = CYAN, width: float = 125) -> str:
    return f'<rect x="{x}" y="{y}" width="4" height="42" fill="{color}"/>{text(x + 12, y + 13, label, 10, fill="#ffffffcc", weight=700)}{fitted_text(x + 12, y + 39, value, 20, width - 12, weight=700)}'


def _scenario_panel(scenario: dict, y: float = 860) -> str:
    points = scenario.get("points") or []
    gap = 10
    card_width = (711 - gap * max(0, len(points) - 1)) / max(1, len(points))
    cards = []
    for index, point in enumerate(points):
        x = 642 + index * (card_width + gap)
        selected = bool(point.get("selected"))
        color = PINK if selected else CYAN
        cards.append(
            f'<g data-role="scenario-point" data-selected="{str(selected).lower()}"><rect x="{x}" y="{y + 59}" width="{card_width}" height="81" rx="12" fill="{color}18" stroke="{color if selected else "#ffffff24"}" stroke-width="{2 if selected else 1}"/>{text(x + card_width / 2, y + 84, number(point["accuracy"], 2) + "%", 11, fill="#ffffffbb", anchor="middle", weight=700)}{text(x + card_width / 2, y + 119, number(point["pp"], 1), 22, fill=color, anchor="middle", weight=700)}{text(x + card_width / 2, y + 134, "PP", 8, fill="#ffffff88", anchor="middle")}</g>'
        )
    summary = f"目标 {number(scenario['pp'], 1)} PP · {number(scenario['stars'], 2)}★"
    return f'<g data-role="performance-scenario">{_panel(612, y, 771, 158)}{text(642, y + 27, "PP 情景计算", 16, weight=700)}{text(642, y + 48, scenario["label"], 10, fill="#ffffffbb")}{text(1355, y + 30, summary, 15, fill=PINK, anchor="end", weight=700)}{"".join(cards)}</g>'


def build_map_svg(payload: dict, *, external_background: bool = False) -> tuple[str, int]:
    beatmapset, beatmap = payload["set"], payload["map"]
    mods = [str(mod) for mod in beatmap.get("mods") or [] if str(mod).upper() != "NM"]
    stats = beatmap.get("stats") or []
    star_delta = float(beatmap.get("stars") or 0) - float(beatmap.get("original_stars") or 0)
    has_star_change = abs(star_delta) >= 0.005
    star_value_color = "#ff6b81" if star_delta > 0.005 else "#63d98b" if star_delta < -0.005 else "#ffffff"
    stats_panel_y = 200
    stats_panel_height = 468
    stats_start_y = stats_panel_y + 57
    stats_area_bottom = 592
    stats_step = (stats_area_bottom - stats_start_y) / max(1, len(stats))
    tag_value = beatmapset.get("tags") or []
    if isinstance(tag_value, list):
        tag_value = " ".join(str(item) for item in tag_value)
    tag_lines = _wrap_text(tag_value, 520, 11)
    scenario = payload.get("scenario")
    height = max(1038 if scenario else 860, 790 + len(tag_lines) * 17)
    objects = (beatmap.get("circles") or 0, beatmap.get("sliders") or 0, beatmap.get("spinners") or 0)
    total_objects = max(1, sum(objects))
    dimension_max = 11 if any(max(float(stat["before"] or 0), float(stat["after"] or 0)) > 10 for stat in stats) else 10
    stats_svg = []
    for index, stat in enumerate(stats):
        y = stats_start_y + index * stats_step
        before, after = float(stat["before"] or 0), float(stat["after"] or 0)
        changed = abs(before - after) > 0.01
        maximum = dimension_max
        start_x, track_width = 720, 560
        row_middle = y + stats_step / 2
        origin = (
            f'<circle cx="{start_x + before / maximum * track_width}" cy="{row_middle}" r="5" '
            f'fill="#0b1622" stroke="{CYAN}" stroke-width="2"/>'
            if changed
            else ""
        )
        stats_svg.append(
            f'<line x1="632" y1="{y}" x2="1363" y2="{y}" stroke="#ffffff13"/><line x1="{start_x}" y1="{row_middle}" x2="{start_x + track_width}" y2="{row_middle}" stroke="#ffffff30" stroke-width="2"/><line x1="{start_x}" y1="{row_middle - 5}" x2="{start_x}" y2="{row_middle + 5}" stroke="#ffffff35"/><line x1="{start_x + track_width / 2}" y1="{row_middle - 5}" x2="{start_x + track_width / 2}" y2="{row_middle + 5}" stroke="#ffffff35"/><line x1="{start_x + track_width}" y1="{row_middle - 5}" x2="{start_x + track_width}" y2="{row_middle + 5}" stroke="#ffffff35"/>{text(645, row_middle - 3, stat["key"], 18, weight=700)}{text(645, row_middle + 15, stat["name"], 10, fill="#ffffffcc")}{origin}<rect x="{start_x + after / maximum * track_width - 5}" y="{row_middle - 5}" width="10" height="10" transform="rotate(45 {start_x + after / maximum * track_width} {row_middle})" fill="{PINK if changed else CYAN}"/>{text(1355, row_middle + 6, number(after, 1), 20, fill=PINK if changed else "#fff", anchor="end", weight=700)}'
        )
    object_x = 720
    object_width = 480
    cursor = object_x
    object_colors = (CYAN, PINK, "#ffc24d")
    object_bar = []
    for count, color in zip(objects, object_colors):
        width = count / total_objects * object_width
        object_bar.append(f'<rect x="{cursor}" y="616" width="{width}" height="10" fill="{color}"/>')
        cursor += width
    title_mods_svg = ""
    if mods:
        mod_icon_size, mod_max_width = 28, 400
        mod_icon_width = mod_icon_size * 45 / 32
        visible_mods = mods[: int(mod_max_width // mod_icon_width)]
        mods_width = len(visible_mods) * mod_icon_width
        mods_x = 1360 - mods_width
        title_mods_svg = f'<g data-role="map-title-mods">{mod_strip(visible_mods, {}, x=mods_x, y=140, icon_size=mod_icon_size, max_width=mods_width, preserve_artwork_ratio=True)}</g>'
    stats_header = f"""
{text(646, stats_panel_y + 29, "谱面参数 · 模组前后对比" if has_star_change else "谱面参数", 16, weight=700)}
{text(720, stats_panel_y + 53, "0", 9, fill="#ffffff99", anchor="middle")}{text(1000, stats_panel_y + 53, number(dimension_max / 2, 1), 9, fill="#ffffff99", anchor="middle")}{text(1280, stats_panel_y + 53, number(dimension_max), 9, fill="#ffffff99", anchor="middle")}{text(1355, stats_panel_y + 53, "当前", 9, fill="#ffffff99", anchor="end")}
"""
    overview_y = 590
    tags_svg = text(41, overview_y + 154, "标签", 10, fill=CYAN, weight=700)
    tags_svg += "".join(
        text(41, overview_y + 178 + line_index * 17, line, 11, fill="#ffffffcc")
        for line_index, line in enumerate(tag_lines)
    )
    scenario_svg = _scenario_panel(scenario) if scenario else ""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">{_background(beatmapset.get("cover"), height, "map", external_canvas=external_background)}
{text(25, 29, "OSU! / 谱面资料", 11, fill=CYAN, weight=700)}{text(1375, 29, f"谱面 {beatmap['id']} · 谱面组 {beatmapset['id']}", 13, anchor="end", weight=700)}
{_left_identity(payload, map_card=True, card_height=height - 78)}
{text(41, overview_y, "谱面概览", 17, weight=700)}{text(570, overview_y, f"谱面 {beatmap['id']}", 10, anchor="end")}
{_metric(41, overview_y + 25, "游玩次数", number(beatmap.get("plays")), width=220)}{_metric(305, overview_y + 25, "通过次数", number(beatmap.get("passes")), color=PINK, width=220)}
{_metric(41, overview_y + 88, "通过率", number((beatmap.get("passes") or 0) / max(1, beatmap.get("plays") or 0) * 100, 1) + "%", width=220)}{_metric(305, overview_y + 88, "收藏", number(beatmapset.get("favourites")), color=PINK, width=220)}
<g data-role="map-tags">{tags_svg}</g>
<defs><clipPath id="map-title-card-clip"><rect x="612" y="61" width="771" height="128" rx="22"/></clipPath></defs>{_panel(612, 61, 771, 128, radius=22)}<rect data-role="map-title-accent" x="612" y="61" width="8" height="128" fill="{PINK}" clip-path="url(#map-title-card-clip)"/>
{text(643, 87, "BEATMAP / DIFFICULTY DETAIL", 9, fill=CYAN)}{fitted_text(643, 133, beatmap["version"], 34, 440, weight=700)}{text(643, 163, MODE_NAMES[int(beatmap["mode_int"])], 14, fill="#ffffffcc")}{title_mods_svg}
{text(1170, 91, "星数", 9, fill="#ffffffcc", anchor="end")}{text(1170, 119, number(beatmap["stars"], 2) + "★", 19, fill=star_value_color, anchor="end", weight=700)}{text(1270, 91, "SS PP", 9, fill="#ffffffcc", anchor="end")}{text(1270, 119, number(beatmap["ss_pp"], 1), 19, fill=CYAN, anchor="end", weight=700)}{text(1360, 91, "最大连击", 9, fill="#ffffffcc", anchor="end")}{text(1360, 119, number(beatmap["max_combo"]) + "x", 19, anchor="end", weight=700)}
<g data-role="map-stats-panel">{_panel(612, stats_panel_y, 771, stats_panel_height)}{stats_header}{"".join(stats_svg)}<line x1="632" y1="592" x2="1363" y2="592" stroke="#ffffff1a"/><g data-role="object-composition">{text(646, 625, "物件构成", 11, fill="#ffffffcc", weight=700)}{"".join(object_bar)}{text(1360, 625, f"{payload['map']['object_labels'][0]} {number(objects[0])}  ·  {payload['map']['object_labels'][1]} {number(objects[1])}  ·  {payload['map']['object_labels'][2]} {number(objects[2])}", 10, anchor="end")}</g></g>
{_panel(612, 679, 771, 164)}{_metric(642, 711, "BPM", number(beatmap["bpm"], 1), width=180)}{_metric(880, 711, "时长", beatmap["duration"], color=PINK, width=180)}{_metric(1118, 711, "物件数", number(beatmap["objects"]), width=180)}{_metric(642, 777, "最大连击", number(beatmap["max_combo"]) + "x", color=PINK, width=180)}{_metric(880, 777, "谱面 ID", str(beatmap["id"]), width=180)}{_metric(1118, 777, "谱面组 ID", str(beatmapset["id"]), color=PINK, width=180)}{scenario_svg}</svg>"""
    return svg, height


def _mix_color(first: str, second: str, first_ratio: float) -> str:
    first_rgb = tuple(int(first[index : index + 2], 16) for index in (1, 3, 5))
    second_rgb = tuple(int(second[index : index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(round(left * first_ratio + right * (1 - first_ratio)) for left, right in zip(first_rgb, second_rgb))
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def _wrap_text(value: object, max_width: float, size: int) -> list[str]:
    """Wrap every character of a label without silently dropping trailing tags."""
    words = str(value or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if text_width(candidate, size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        while text_width(word, size) > max_width:
            split_at = len(word)
            while split_at > 1 and text_width(word[:split_at], size) > max_width:
                split_at -= 1
            lines.append(word[:split_at])
            word = word[split_at:]
        current = word
    if current:
        lines.append(current)
    return lines


def _mode_glyph(mode: int, x: float, y: float, color: str) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Extra" font-size="25" font-weight="400" '
        f'text-anchor="middle" fill="{color}" data-font="extra">{escape_text(MODE_GLYPHS[mode])}</text>'
    )


def _spectrum_svg(difficulties: list[dict], minimum: float, maximum: float) -> str:
    track_x, track_width, track_y = 610.0, 590.0, 237.0
    distance = maximum - minimum
    values = [minimum]
    values.extend(value for value, _ in STAR_STOPS if minimum < value < maximum)
    if maximum != minimum:
        values.append(maximum)
    gradient_stops = []
    for value in values:
        offset = 0.5 if distance == 0 else (value - minimum) / distance
        gradient_stops.append(f'<stop offset="{offset:.4f}" stop-color="{star_color(value)}"/>')
    nodes = []
    for index, item in enumerate(difficulties):
        stars = float(item["stars"])
        ratio = 0.5 if distance == 0 else (stars - minimum) / distance
        x = track_x + max(0.0, min(1.0, ratio)) * track_width
        color = star_color(stars)
        nodes.append(
            f'<g data-role="spectrum-node" data-index="{index}"><rect x="{x - 1}" y="{track_y - 8}" width="2" height="16" rx="1" fill="{color}"/><rect x="{x - 6}" y="{track_y - 1}" width="12" height="2" rx="1" fill="{color}"/></g>'
        )
    return f"""
<defs><linearGradient id="bmap-spectrum-gradient" x1="0" y1="0" x2="1" y2="0">{"".join(gradient_stops)}</linearGradient></defs>
<rect x="{track_x}" y="{track_y - 1}" width="{track_width}" height="2" rx="1" fill="url(#bmap-spectrum-gradient)"/>{"".join(nodes)}
"""


def _difficulty_row(item: dict, index: int, y: float, show_mappers: bool) -> str:
    color = star_color(float(item["stars"]))
    pass_rate = float(item.get("passes") or 0) / max(1, float(item.get("plays") or 0)) * 100
    row_gradient = f"bmap-row-bg-{index}"
    row_start = _mix_color(color, "#12202a", 0.28)
    row_end = _mix_color(color, "#15202c", 0.10)
    owner_parts: list[str] = []
    if show_mappers:
        for owner_index, owner in enumerate(item.get("owners", [])[:3]):
            cx = 856 + owner_index * 21
            clip_id = f"owner-{index}-{owner_index}"
            owner_parts.append(
                f'<defs><clipPath id="{clip_id}"><circle cx="{cx}" cy="{y + 29}" r="15"/></clipPath></defs><circle cx="{cx}" cy="{y + 29}" r="16" fill="#152430" stroke="{color}" stroke-width="2"/>{image(owner.get("avatar"), cx - 15, y + 14, 30, 30, clip=clip_id)}'
            )
    version_width = 240 if show_mappers else 300
    params = []
    for param_index, (label, value) in enumerate(
        (("CS", item["cs"]), ("AR", item["ar"]), ("OD", item["od"]), ("HP", item["hp"]))
    ):
        x = 1186 + param_index * 44
        params.append(
            f'<rect data-role="difficulty-param" x="{x}" y="{y + 18}" width="42" height="22" fill="#ffffff16" stroke="#ffffff30"/>{text(x + 21, y + 33, f"{label} {number(value, 1)}", 8, anchor="middle", weight=700)}'
        )
    star_x = 926
    return f"""
<defs><linearGradient id="{row_gradient}" x1="0" y1="0" x2="1" y2="0"><stop stop-color="{row_start}"/><stop offset="1" stop-color="{row_end}"/></linearGradient><clipPath id="bmap-row-clip-{index}"><rect x="436" y="{y}" width="947" height="58" rx="13"/></clipPath></defs>
<rect data-role="difficulty-row" x="436" y="{y}" width="947" height="58" rx="13" fill="url(#{row_gradient})" stroke="#ffffff17"/><rect data-role="difficulty-accent" x="436" y="{y}" width="7" height="58" fill="{color}" clip-path="url(#bmap-row-clip-{index})"/>
{text(468, y + 35, str(index + 1).zfill(2), 11, fill="#ffffffbb")}{_mode_glyph(int(item["mode"]), 504, y + 39, color)}
{fitted_text(530, y + 27, item["version"], 17, version_width, weight=700)}{text(530, y + 46, f"谱面 {item['id']} · {item['length']}", 10, fill="#ffffffcc")}{"".join(owner_parts)}
<rect x="{star_x}" y="{y + 15}" width="76" height="28" rx="14" fill="#050d16b8" stroke="{color}"/>{text(star_x + 38, y + 35, "★ " + number(item["stars"], 2), 13, fill="#ffd966" if float(item["stars"]) >= 6.5 else color, anchor="middle", weight=700)}
{text(1018, y + 22, "最大连击", 9, fill="#ffffffcc")}{text(1018, y + 42, number(item.get("combo")) + "x", 14, weight=700)}
{text(1108, y + 20, "通过率", 9, fill="#ffffffcc")}{text(1108, y + 39, number(pass_rate, 1) + "%", 13, weight=700)}<rect data-role="pass-track" x="1108" y="{y + 47}" width="62" height="3" rx="1.5" fill="#ffffff2a"/><rect data-role="pass-progress" x="1108" y="{y + 47}" width="{62 * min(100, pass_rate) / 100:.2f}" height="3" rx="1.5" fill="{color}"/>
{"".join(params)}
"""


def build_bmap_svg(payload: dict) -> tuple[str, int]:
    beatmapset = payload["set"]
    difficulties = payload["difficulties"][:20]
    tag_value = beatmapset.get("tags") or ""
    if isinstance(tag_value, list):
        tag_value = " ".join(str(item) for item in tag_value)
    tag_lines = _wrap_text(tag_value, 335, 11)
    extra_rows = max(0, len(difficulties) - 9)
    height = max(900 + extra_rows * 65, 790 + len(tag_lines) * 17)
    minimum, maximum = float(difficulties[0]["stars"]), float(difficulties[-1]["stars"])
    average = sum(float(item["stars"]) for item in difficulties) / len(difficulties)
    rows_y = 300
    rows = "".join(
        _difficulty_row(item, index, rows_y + index * 65, payload["show_difficulty_owners"])
        for index, item in enumerate(difficulties)
    )
    overview_y = 500
    tags_svg = text(41, overview_y + 218, "标签", 10, fill=CYAN, weight=700)
    tags_svg += "".join(
        text(41, overview_y + 242 + line_index * 17, line, 11, fill="#ffffffcc")
        for line_index, line in enumerate(tag_lines)
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">{_background(beatmapset.get("cover"), height, "bmap")}
{text(25, 29, "OSU! / 谱面组资料", 11, fill=CYAN, weight=700)}{text(1375, 29, f"谱面组 · {beatmapset['id']}", 13, anchor="end", weight=700)}
{_left_identity(payload, map_card=False, card_height=height - 78)}
{text(41, overview_y, "谱面组概览", 17, weight=700)}{text(380, overview_y, "上架于 " + beatmapset["ranked_date"], 10, anchor="end")}
{_metric(41, overview_y + 28, "平均星数", number(average, 2) + "★", width=150)}{_metric(215, overview_y + 28, "基准 BPM", number(beatmapset["bpm"], 1), color=PINK, width=150)}
{_metric(41, overview_y + 91, "累计游玩", number(beatmapset["plays"]), width=150)}{_metric(215, overview_y + 91, "累计通过", number(beatmapset["passes"]), color=PINK, width=150)}
{_metric(41, overview_y + 154, "收藏", number(beatmapset["favourites"]), width=150)}{_metric(215, overview_y + 154, "完整时长", beatmapset["duration"], color=PINK, width=150)}
{tags_svg}
<defs><clipPath id="bmap-title-card-clip"><rect x="436" y="61" width="947" height="130" rx="22"/></clipPath></defs><rect data-role="title-card" x="436" y="61" width="947" height="130" rx="22" fill="#08141fc9" stroke="#ffffff22"/><rect data-role="title-accent" x="436" y="61" width="8" height="130" fill="{PINK}" clip-path="url(#bmap-title-card-clip)"/>{text(467, 88, "BEATMAPSET / DIFFICULTY COLLECTION", 9, fill=CYAN)}{fitted_text(467, 133, beatmapset["title"], 35, 555, weight=700)}{fitted_text(467, 163, beatmapset["artist"], 15, 555, fill="#ffffffcc")}
{text(1120, 91, "难度数量", 9, fill="#ffffffcc", anchor="end")}{text(1120, 119, f"{payload.get('difficulty_count', len(payload['difficulties']))} 张", 17, anchor="end", weight=700)}{text(1235, 91, "最高星数", 9, fill="#ffffffcc", anchor="end")}{text(1235, 119, number(maximum, 2) + "★", 17, anchor="end", weight=700)}{text(1360, 91, "累计通过", 9, fill="#ffffffcc", anchor="end")}{text(1360, 119, number(beatmapset["passes"]), 17, anchor="end", weight=700)}
<rect x="436" y="202" width="947" height="70" fill="#08141fc9"/><line x1="436" y1="202" x2="1383" y2="202" stroke="{CYAN}" opacity=".6"/><line x1="436" y1="272" x2="1383" y2="272" stroke="{PINK}" opacity=".5"/>{text(460, 226, "难度光谱", 13, weight=700)}{text(460, 248, f"{len(difficulties)} 个节点", 9, fill="#ffffffbb")}{_spectrum_svg(difficulties, minimum, maximum)}{text(1360, 241, f"{minimum:.2f}–{maximum:.2f}★", 14, anchor="end", weight=700)}
{text(468, 290, "#", 9, fill="#ffffff99")}{text(504, 290, "模式", 9, fill="#ffffff99", anchor="middle")}{text(530, 290, "难度 / 谱师", 9, fill="#ffffff99")}{text(964, 290, "星数", 9, fill="#ffffff99", anchor="middle")}{text(1018, 290, "最大连击", 9, fill="#ffffff99")}{text(1108, 290, "通过率", 9, fill="#ffffff99")}{text(1186, 290, "谱面参数", 9, fill="#ffffff99")}
{rows}</svg>"""
    return svg, height


async def render_map_svg(payload: dict):
    cover = payload["set"].get("cover")
    svg, height = build_map_svg(payload, external_background=bool(cover))
    return await render_svg_jpeg_async(
        svg,
        width=WIDTH,
        height=height,
        quality=92,
        image_rendering="optimize_speed",
        background_data_uri=cover,
    )


async def render_bmap_svg(payload: dict):
    svg, height = build_bmap_svg(payload)
    return await render_svg_jpeg_async(svg, width=WIDTH, height=height, quality=92)
