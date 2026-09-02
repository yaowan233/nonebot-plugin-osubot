"""Native SVG renderers for beatmap and beatmapset information cards."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from .svg_components import STAR_STOPS, fitted_text, image, mod_strip, number, star_color, text
from .svg_render import escape_text, render_svg_jpeg_async, text_width, truncate_text


WIDTH = 1400
MAP_WIDTH = 1440
MAP_HEIGHT = 920
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


def _build_map_svg_legacy(payload: dict, *, external_background: bool = False) -> tuple[str, int]:
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


def _map_panel(
    x: float, y: float, width: float, height: float, *, radius: float = 16, stroke: str = "#ffffff22"
) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="#08131fee" stroke="{stroke}"/>'


def _section_title(x: float, y: float, value: str, *, hint: str = "", right: float | None = None) -> str:
    suffix = text(right, y, hint, 9, fill="#8292a3", anchor="end") if hint and right is not None else ""
    return f'<rect x="{x}" y="{y - 12}" width="3" height="13" rx="1.5" fill="{CYAN}"/>{text(x + 12, y, value, 13, weight=700)}{suffix}'


def _sample_bars(values: list[float] | tuple[float, ...], count: int = 24) -> list[float]:
    if not values:
        return []
    numeric = [max(0.0, float(value or 0)) for value in values]
    if len(numeric) <= count:
        return numeric
    sampled = []
    for index in range(count):
        start = round(index * len(numeric) / count)
        end = max(start + 1, round((index + 1) * len(numeric) / count))
        sampled.append(max(numeric[start:end]))
    return sampled


def _map_cover_card(payload: dict) -> str:
    beatmapset, beatmap = payload["set"], payload["map"]
    title = beatmapset.get("title_unicode") or beatmapset.get("title") or ""
    artist = beatmapset.get("artist_unicode") or beatmapset.get("artist") or ""
    status = STATUS_NAMES.get(str(beatmapset.get("status") or "").lower(), str(beatmapset.get("status") or ""))
    cover = beatmapset.get("cover")
    mods = [str(value).upper() for value in beatmap.get("mods") or [] if str(value).upper() != "NM"]
    tags = " ".join(str(value) for value in beatmapset.get("tags") or [])
    plays = float(beatmap.get("plays") or 0)
    passes = float(beatmap.get("passes") or 0)
    pass_rate = passes / max(1.0, plays) * 100
    mods_svg = (
        mod_strip(
            mods,
            {},
            x=574 - min(len(mods), 5) * (28 * 45 / 32),
            y=101,
            icon_size=28,
            max_width=210,
            preserve_artwork_ratio=True,
        )
        if mods
        else ""
    )
    return f"""
<defs><clipPath id="map-cover-clip"><rect x="42" y="86" width="548" height="205" rx="12"/></clipPath><clipPath id="map-avatar-clip"><circle cx="76" cy="401" r="22"/></clipPath></defs>
{_map_panel(26, 70, 580, 385)}
{image(cover, 42, 86, 548, 205, clip="map-cover-clip")}<rect x="42" y="86" width="548" height="205" rx="12" fill="#020711" opacity=".34"/>
<rect x="57" y="101" width="116" height="25" rx="6" fill="#06101bdd" stroke="#45dca888"/>{text(115, 118, "● " + status, 10, fill="#45dca8", anchor="middle", weight=700)}
{mods_svg}{fitted_text(58, 252, title, 32, 500, weight=700)}{fitted_text(58, 278, artist, 14, 315, fill="#e2e8f0", weight=700)}
{fitted_text(574, 278, ("来源: " + str(beatmapset.get("source"))) if beatmapset.get("source") else "原创曲目", 14, 260, fill="#e2e8f0", anchor="end", weight=700)}
<line x1="42" y1="323" x2="590" y2="323" stroke="#ffffff18"/><g data-role="map-tags">{text(42, 342, "标签", 9, fill=CYAN, weight=700)}{text(72, 342, truncate_text(tags or "无标签", 500, 9), 9, fill="#9cabb8")}</g>
<rect x="42" y="365" width="548" height="72" rx="10" fill="#ffffff08" stroke="#ffffff12"/>
<circle cx="76" cy="401" r="25" fill="#0d1e2a" stroke="{CYAN}" stroke-width="2"/>{image(beatmapset.get("avatar"), 54, 379, 44, 44, clip="map-avatar-clip")}
{text(108, 391, "谱面作者", 9, fill="#8292a3")}{fitted_text(108, 413, beatmapset.get("creator") or "—", 16, 220, weight=700)}
{text(438, 390, "游玩次数", 8, fill="#8292a3", anchor="end")}{text(438, 411, number(plays), 14, anchor="end", weight=700)}
{text(508, 390, "通过率", 8, fill="#8292a3", anchor="end")}{text(508, 411, number(pass_rate, 1) + "%", 14, anchor="end", weight=700)}
{text(572, 390, "收藏", 8, fill="#8292a3", anchor="end")}{text(572, 411, "♥ " + number(beatmapset.get("favourites")), 14, fill=PINK, anchor="end", weight=700)}
"""


def _pp_component_items(beatmap: dict) -> list[tuple[str, float]]:
    components = beatmap.get("pp_components") or {}
    mode = int(beatmap.get("mode_int") or 0)
    if mode == 0:
        return [
            ("瞄准", components.get("aim", 0)),
            ("速度", components.get("speed", 0)),
            ("判定", components.get("accuracy", 0)),
        ]
    if mode == 1:
        return [("难度", components.get("difficulty", 0)), ("判定", components.get("accuracy", 0))]
    if mode == 2:
        return [("接果", components.get("catch", beatmap.get("ss_pp", 0)))]
    return [("难度", components.get("difficulty", beatmap.get("ss_pp", 0)))]


def _map_hero(payload: dict) -> str:
    beatmap = payload["map"]
    mode = int(beatmap.get("mode_int") or 0)
    mode_names = ("主模式 (osu!)", "太鼓模式 (taiko)", "接水果模式 (catch)", "下落模式 (mania)")
    stars = float(beatmap.get("stars") or 0)
    original_stars = float(beatmap.get("original_stars") or stars)
    delta = stars - original_stars
    has_delta = abs(delta) >= 0.005
    badge_color = star_color(stars)
    if stars >= 9:
        badge_color = "#e11d48"
    panel_x, panel_width = (646, 332) if has_delta else (646, 0)
    pp_x = 992 if has_delta else 646
    pp_width = 400 if has_delta else 746
    ss_pp_text = number(beatmap.get("ss_pp"), 1)
    ss_pp_unit_x = pp_x + 22 + text_width(ss_pp_text, 38)
    delta_panel = ""
    if has_delta:
        sign = "+" if delta > 0 else ""
        delta_panel = f"""<g data-role="star-change-card">{_map_panel(panel_x, 205, panel_width, 115, radius=12)}{text(panel_x + 15, 228, "难度星级评定", 11, fill="#95a3b3")}{text(panel_x + panel_width - 15, 228, f"{sign}{delta / max(original_stars, 0.1) * 100:.1f}% 增幅", 11, fill=CYAN, anchor="end", weight=700)}<rect x="{panel_x + 15}" y="242" width="66" height="23" rx="6" fill="#ff2a8528" stroke="#ff4f9688"/>{text(panel_x + 48, 258, "★ " + sign + number(delta, 2), 11, fill="#ff69aa", anchor="middle", weight=700)}{text(panel_x + 91, 258, "原始星级 " + number(original_stars, 2) + "★", 10, fill="#8997a7")}<line x1="{panel_x + 15}" y1="279" x2="{panel_x + panel_width - 15}" y2="279" stroke="#ffffff12"/>{text(panel_x + 15, 304, "模组加成: " + ", ".join(beatmap.get("mods") or []), 10, fill="#b9c5cf", weight=700)}</g>"""
    components = _pp_component_items(beatmap)
    component_text = []
    for index, (label, value) in enumerate(components):
        x = pp_x + 16 + index * ((pp_width - 32) / max(1, len(components) - 1)) if len(components) > 1 else pp_x + 16
        anchor = "start" if index == 0 else "end" if index == len(components) - 1 else "middle"
        component_text.append(
            text(x, 304, f"{label}: {number(value, 0)} PP", 10, fill="#dce5ec", anchor=anchor, weight=700)
        )
    quick = []
    quick_values = (
        ("速度 (BPM)", number(beatmap.get("bpm"), 1), CYAN),
        ("谱面时长", str(beatmap.get("duration") or "—"), PINK),
        ("最大连击", number(beatmap.get("max_combo")) + "x", "#f6b943"),
        ("物件总数", number(beatmap.get("objects")), "#a78bfa"),
    )
    for index, (label, value, color) in enumerate(quick_values):
        x = 646 + index * 188
        quick.append(
            f'<rect x="{x}" y="378" width="177" height="55" rx="8" fill="#ffffff08" stroke="#ffffff12"/><rect x="{x}" y="386" width="3" height="39" rx="1.5" fill="{color}"/>{text(x + 12, 397, label, 9, fill="#8292a3")}{text(x + 12, 421, value, 16, weight=700)}'
        )
    return f"""
{_map_panel(624, 70, 790, 385)}<rect x="624" y="70" width="790" height="122" rx="16" fill="#0b1222bb"/>
{text(646, 101, "当前难度详情  /  " + mode_names[mode], 10, fill=CYAN, weight=700)}{fitted_text(646, 145, beatmap.get("version") or "Difficulty", 36, 620, weight=700)}
<rect x="1290" y="88" width="98" height="39" rx="12" fill="{badge_color}" stroke="#ffffff66"/>{text(1339, 115, "★ " + number(stars, 2), 20, fill="#101925" if stars < 6.5 else "#fff", anchor="middle", weight=700)}
{delta_panel}{_map_panel(pp_x, 205, pp_width, 115, radius=12, stroke="#ffffff30")}{text(pp_x + 16, 228, "满分表现值 (SS 100.00%)", 11, fill="#95a3b3")}{text(pp_x + pp_width - 16, 228, "预估表现", 11, anchor="end", weight=700)}{text(pp_x + 16, 270, ss_pp_text, 38, fill="#f6b923", weight=700)}{text(ss_pp_unit_x, 270, "PP", 13, fill="#f6b923", weight=700)}<line x1="{pp_x + 16}" y1="282" x2="{pp_x + pp_width - 16}" y2="282" stroke="#ffffff12"/>{"".join(component_text)}{"".join(quick)}
"""


def _map_rating_and_failures(payload: dict) -> str:
    beatmapset, beatmap = payload["set"], payload["map"]
    rating = beatmap.get("rating")
    votes = int(beatmap.get("rating_votes") or 0)
    rating_values = [float(value or 0) for value in (beatmap.get("rating_distribution") or [])]
    rating_values = rating_values[1:] if len(rating_values) > 10 else rating_values
    rating_max = max(rating_values, default=0)
    rating_bars = []
    for index, value in enumerate(rating_values[-10:]):
        if value <= 0:
            continue
        height = max(2, 30 * value / rating_max)
        rating_bars.append(
            f'<rect x="{110 + index * 9}" y="{578 - height}" width="6" height="{height}" rx="2" fill="#f6b923"/>'
        )
    raw_failures = [float(value or 0) for value in (beatmap.get("fail_points") or [])]
    failures = _sample_bars(raw_failures)
    failure_max = max(failures, default=0)
    has_failure_data = failure_max > 0
    peak_index = max(range(len(raw_failures)), key=raw_failures.__getitem__) if raw_failures else -1
    peak_pct = round((peak_index + 0.5) / len(raw_failures) * 100) if raw_failures else 0
    fail_bars = []
    for index, value in enumerate(failures):
        if value <= 0:
            continue
        height = max(2, 27 * value / failure_max)
        color = CYAN if value == failure_max else PINK
        fail_bars.append(
            f'<rect x="{250 + index * 10}" y="{576 - height}" width="7" height="{height}" rx="2" fill="{color}"/>'
        )
    rating_text = number(rating, 1) if rating is not None else "—"
    return f"""
{text(48, 535, "玩家评价", 9, fill="#8292a3")}{text(190, 535, number(votes) + " 次评分" if votes else "暂无评分", 8, fill="#8292a3", anchor="end")}{text(48, 577, rating_text, 27, fill="#f6b923", weight=700)}{text(91, 577, "/10", 8, fill="#8292a3")}{"".join(rating_bars)}
<line x1="205" y1="520" x2="205" y2="588" stroke="#ffffff18"/>{text(224, 535, "失败位置分布", 9, fill="#8292a3")}{text(478, 535, "峰值 " + str(peak_pct) + "%" if has_failure_data else "暂无数据", 8, fill="#8292a3", anchor="end")}{"".join(fail_bars)}{text(224, 589, "开头", 7, fill="#657587")}{text(352, 589, "50%", 7, fill="#657587", anchor="middle")}{text(478, 589, "结尾", 7, fill="#657587", anchor="end")}
<line x1="492" y1="520" x2="492" y2="588" stroke="#ffffff18"/>{text(510, 535, "流派", 8, fill="#8292a3")}{fitted_text(510, 552, beatmapset.get("genre") or "其他", 10, 95, weight=700)}{text(620, 535, "语言", 8, fill="#8292a3")}{fitted_text(620, 552, beatmapset.get("language") or "其他", 10, 88, weight=700)}{text(510, 570, "提名", 8, fill="#8292a3")}{fitted_text(510, 587, beatmapset.get("nominations") or "暂无", 10, 198, weight=700)}
"""


def _map_params(payload: dict) -> str:
    stats = payload["map"].get("stats") or []
    if not stats:
        return ""
    parts = []
    step = min(58, 230 / max(1, len(stats)))
    for index, stat in enumerate(stats):
        y = 611 + index * step
        before = float(stat.get("before") or 0)
        after = float(stat.get("after") or 0)
        changed = abs(after - before) > 0.01
        maximum = 11.0
        track_x, track_width = 180, 410
        key = str(stat.get("key") or "")
        name = str(stat.get("name") or "")
        name_x = max(91, 60 + text_width(key, 14) + 8)
        name_x = min(name_x, track_x - text_width(name, 9) - 8)
        before_x = track_x + min(before, maximum) / maximum * track_width
        after_x = track_x + min(after, maximum) / maximum * track_width
        origin = (
            f'<circle cx="{before_x}" cy="{y + 25}" r="4" fill="#08131f" stroke="{CYAN}" stroke-width="2"/>'
            if changed
            else ""
        )
        parts.append(
            f'<rect x="48" y="{y}" width="685" height="49" rx="8" fill="#ffffff07" stroke="#ffffff10"/>{text(60, y + 23, key, 14, weight=700)}{text(name_x, y + 23, name, 9, fill="#9aa8b7")}<line x1="{track_x}" y1="{y + 25}" x2="{track_x + track_width}" y2="{y + 25}" stroke="#ffffff20" stroke-width="6"/>{origin}<rect x="{after_x - 5}" y="{y + 20}" width="10" height="10" transform="rotate(45 {after_x} {y + 25})" fill="{PINK if changed else CYAN}"/>{text(717, y + 29, (number(before, 1) + " → " if changed else "") + number(after, 1), 15, fill=PINK if changed else "#fff", anchor="end", weight=700)}'
        )
    return "".join(parts)


def _map_analysis(payload: dict) -> str:
    beatmap = payload["map"]
    scenario = payload.get("scenario")
    points = (scenario or {}).get("points") or beatmap.get("pp_matrix") or []
    points = points[:5]
    cards = []
    max_pp = max((float(point.get("pp") or 0) for point in points), default=1)
    card_width = (597 - max(0, len(points) - 1) * 8) / max(1, len(points))
    for index, point in enumerate(points):
        selected = bool(point.get("selected")) or (not scenario and index == 0)
        x = 795 + index * (card_width + 8)
        stroke = "#f6b923" if selected else "#ffffff20"
        fill = "#f6b92312" if selected else "#ffffff07"
        value_color = "#f6b923" if selected else "#fff"
        label = (
            text(x + card_width / 2, 522, "当前目标", 8, fill="#211603", anchor="middle", weight=700)
            if selected
            else ""
        )
        label_bg = (
            f'<rect x="{x + card_width / 2 - 28}" y="510" width="56" height="16" rx="4" fill="#f6b923"/>'
            if selected
            else ""
        )
        bar_width = (card_width - 28) * float(point.get("pp") or 0) / max_pp
        bar_color = stroke if selected else "#dce5ec"
        cards.append(
            f'<g data-role="scenario-point" data-selected="{str(selected).lower()}"><rect x="{x}" y="518" width="{card_width}" height="60" rx="10" fill="{fill}" stroke="{stroke}"/>{label_bg}{label}{text(x + card_width / 2, 540, number(point.get("accuracy"), 1) + "%", 9, fill="#92a0b0", anchor="middle", weight=700)}{text(x + card_width / 2, 562, number(point.get("pp"), 1), 15, fill=value_color, anchor="middle", weight=700)}<rect x="{x + 14}" y="569" width="{card_width - 28}" height="3" rx="1.5" fill="#ffffff18"/><rect x="{x + 14}" y="569" width="{bar_width}" height="3" rx="1.5" fill="{bar_color}"/></g>'
        )
    objects = [float(beatmap.get(key) or 0) for key in ("circles", "sliders", "spinners")]
    total = max(1.0, sum(objects))
    labels = beatmap.get("object_labels") or ("物件 1", "物件 2", "物件 3")
    colors = (CYAN, PINK, "#f6a817")
    cursor = 810.0
    bars = []
    legends = []
    for index, (value, color) in enumerate(zip(objects, colors)):
        width = 567 * value / total
        bars.append(f'<rect x="{cursor}" y="650" width="{width}" height="8" fill="{color}"/>')
        cursor += width
        legends.append(
            text(
                810 + index * 188, 680, f"● {labels[index]} {number(value)} ({value / total * 100:.1f}%)", 8, fill=color
            )
        )
    difficulties = sorted(payload.get("difficulties") or [], key=lambda item: float(item.get("stars") or 0))
    if len(difficulties) > 5:
        current_index = next(
            (index for index, item in enumerate(difficulties) if item.get("current")), len(difficulties) - 1
        )
        start = max(0, min(current_index - 2, len(difficulties) - 5))
        difficulties = difficulties[start : start + 5]
    pills = []
    pill_width = (567 - max(0, len(difficulties) - 1) * 8) / max(1, len(difficulties))
    for index, item in enumerate(difficulties):
        x = 810 + index * (pill_width + 8)
        active = bool(item.get("current"))
        color = star_color(float(item.get("stars") or 0))
        pill_stroke = CYAN if active else "#ffffff18"
        pills.append(
            f'<rect x="{x}" y="786" width="{pill_width}" height="44" rx="8" fill="#ffffff07" stroke="{pill_stroke}"/>{text(x + pill_width / 2, 804, "★ " + number(item.get("stars"), 2), 10, fill=color if float(item.get("stars") or 0) < 6.5 else "#ffd966", anchor="middle", weight=700)}{fitted_text(x + pill_width / 2, 822, item.get("version") or "Difficulty", 8, pill_width - 12, anchor="middle", fill="#aebac5", weight=700)}'
        )
    scenario_hint = scenario.get("label") if scenario else "全连击 (FC) 准确率梯度"
    return f"""<g data-role="performance-scenario">
{_map_panel(773, 465, 641, 405)}{_section_title(795, 495, "PP 表现值情景模拟", hint=truncate_text(scenario_hint, 260, 9), right=1392)}<line x1="795" y1="507" x2="1392" y2="507" stroke="#ffffff16"/>{"".join(cards)}
<rect x="795" y="620" width="597" height="82" rx="10" fill="#ffffff06" stroke="#ffffff10"/>{text(810, 640, "物件构成占比", 9, fill="#8e9dac")}{text(1377, 640, "节奏密度", 8, fill="#738394", anchor="end")}{"".join(bars)}{"".join(legends)}
<rect x="795" y="754" width="597" height="92" rx="10" fill="#ffffff05" stroke="#ffffff10"/>{text(810, 776, "同谱面组难度", 9, fill="#8292a3")}{"".join(pills)}
</g>"""


def build_map_svg(payload: dict, *, external_background: bool = False) -> tuple[str, int]:
    beatmapset, beatmap = payload["set"], payload["map"]
    cover_layer = "" if external_background else image(beatmapset.get("cover"), 0, 0, MAP_WIDTH, MAP_HEIGHT)
    status = STATUS_NAMES.get(str(beatmapset.get("status") or "").lower(), str(beatmapset.get("status") or ""))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{MAP_WIDTH}" height="{MAP_HEIGHT}" viewBox="0 0 {MAP_WIDTH} {MAP_HEIGHT}">{cover_layer}<rect width="{MAP_WIDTH}" height="{MAP_HEIGHT}" fill="#050a12" opacity=".74"/>
{text(26, 33, "OSU!", 11, fill="#fff", weight=700)}<rect x="83" y="17" width="126" height="25" rx="7" fill="#ffffff0d" stroke="#ffffff26"/>{text(146, 34, ("● " + ("主模式 (osu!)", "太鼓模式 (taiko)", "接水果 (catch)", "下落模式 (mania)")[int(beatmap.get("mode_int") or 0)]), 10, fill=CYAN, anchor="middle", weight=700)}{text(225, 34, "谱面详细资料", 10, fill="#8997a7")}<rect x="617" y="17" width="222" height="25" rx="7" fill="#050a12aa" stroke="#ffffff16"/>{text(728, 34, f"谱面 ID: {beatmap.get('id')}  ·  谱面组: {beatmapset.get('id')}", 10, fill="#91a1b1", anchor="middle")}{text(1390, 34, status + (("  ·  " + str(beatmapset.get("ranked_date"))) if beatmapset.get("ranked_date") else ""), 10, fill="#49d8a3", anchor="end", weight=700)}<line x1="26" y1="52" x2="1414" y2="52" stroke="#ffffff18"/>
{_map_cover_card(payload)}{_map_hero(payload)}<g data-role="map-stats-panel">{_map_panel(26, 465, 729, 405)}{_section_title(48, 495, "谱面属性 · 模组前后对比" if abs(float(beatmap.get("stars") or 0) - float(beatmap.get("original_stars") or 0)) >= 0.005 else "谱面属性", hint="数值范围 0 → 11.0", right=733)}<line x1="48" y1="507" x2="733" y2="507" stroke="#ffffff16"/>{_map_rating_and_failures(payload)}{_map_params(payload)}</g>{_map_analysis(payload)}
<line x1="26" y1="887" x2="1414" y2="887" stroke="#ffffff18"/>{text(26, 909, "nonebot-plugin-osubot", 9, fill="#8997a7", weight=700)}{text(1414, 909, "OSU! API V2", 8, fill="#6f8091", anchor="end")}</svg>"""
    return svg, MAP_HEIGHT


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
        width=MAP_WIDTH,
        height=height,
        quality=92,
        image_rendering="optimize_speed",
        background_data_uri=cover,
    )


async def render_bmap_svg(payload: dict):
    svg, height = build_bmap_svg(payload)
    return await render_svg_jpeg_async(svg, width=WIDTH, height=height, quality=92)
