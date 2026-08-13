"""Native SVG renderer for one beatmap's retained score list."""

# SVG geometry is materially clearer when markup remains on one line.
# ruff: noqa: E501

from __future__ import annotations

from .svg_components import fitted_text, image, mod_strip, number, text
from .svg_render import render_svg_jpeg_async


WIDTH = 1400
PINK = "#ff3f8e"
CYAN = "#20a9b8"


def _header(data: dict) -> str:
    user = data["user"]
    beatmap = data["map"]
    return f"""
<defs><clipPath id="history-avatar"><rect x="45" y="71" width="110" height="110" rx="8"/></clipPath><clipPath id="history-map"><rect x="420" y="0" width="980" height="250"/></clipPath><linearGradient id="history-cover-shade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0c1724" stop-opacity=".93"/><stop offset=".65" stop-color="#0c1724" stop-opacity=".63"/><stop offset="1" stop-color="#0c1724" stop-opacity=".78"/></linearGradient></defs>
<rect width="420" height="250" fill="#f0f1ed"/>
<rect width="420" height="4" fill="{PINK}"/><rect x="420" width="980" height="4" fill="{CYAN}"/>
<rect x="55" y="81" width="110" height="110" rx="8" fill="{PINK}"/>
{image(user.get("avatar_data"), 45, 71, 110, 110, clip="history-avatar")}
{text(180, 85, "OSU! 谱面成绩档案", 11, fill="#df347c", weight=700)}
{fitted_text(180, 130, user["name"], 32, 205, fill="#101824", weight=700)}
{text(180, 157, f"{user['country']} · 全球 #{number(user.get('global_rank'))}", 12, fill="#101824", weight=700)}
{text(180, 180, f"{number(user.get('pp'), 1)} pp · UID {user['id']}", 12, fill="#101824", weight=700)}
{image(beatmap.get("cover_data"), 420, 0, 980, 250, clip="history-map")}
<rect x="420" width="980" height="250" fill="url(#history-cover-shade)"/>
{text(468, 52, "BEATMAP MOD SCORES", 11, fill="#54d7df", weight=700)}
{fitted_text(468, 108, beatmap["title"], 40, 820, weight=700)}
{fitted_text(468, 151, beatmap["artist"], 18, 330, weight=700)}
<rect x="561" y="128" width="4" height="33" fill="{PINK}"/>
{fitted_text(576, 151, beatmap["version"], 15, 360, weight=700)}
<rect x="468" y="177" width="88" height="32" rx="17" fill="{beatmap["star_color"]}" stroke="#ffffff66"/>
{text(512, 199, "★ " + number(beatmap["stars"], 2), 14, fill=beatmap["star_text"], anchor="middle", weight=700)}
{_header_fact(568, f"{number(beatmap.get('bpm'))} BPM")}
{_header_fact(650, f"谱师 {beatmap['creator']}", 104)}
{_header_fact(766, f"BID {beatmap['id']}", 96)}
"""


def _header_fact(x: float, value: str, width: float = 70) -> str:
    return f'<rect x="{x}" y="177" width="{width}" height="32" fill="#07111da3" stroke="#ffffff25"/>{fitted_text(x + width / 2, 198, value, 11, width - 10, anchor="middle", weight=700)}'


def _columns() -> str:
    columns = (
        (50, "#"),
        (96, "评级"),
        (158, "分数"),
        (305, "PP"),
        (421, "准确率"),
        (525, "连击"),
        (630, "判定"),
        (943, "MODS"),
        (1135, "星数"),
        (1327, "游玩时间"),
    )
    return "".join(text(x, 294, label, 9, fill="#101824", anchor="middle", weight=700) for x, label in columns)


def _row(play: dict, index: int) -> str:
    y = 315 + index * 102
    best = bool(play.get("best"))
    failed = not bool(play.get("passed", True))
    fill = "#fff2f7" if best else "#fcfaf4"
    opacity = 0.62 if failed else 1
    grade = str(play.get("rank") or "F")
    grade_color = (
        "#dd506b" if grade == "F" else "#72c904" if grade == "A" else "#b8b8b8" if grade in {"S", "SH"} else "#dc9d24"
    )
    judgements = play.get("judgements") or []
    judge_parts: list[str] = []
    judge_width = 270 / max(1, min(4, len(judgements)))
    for judge_index, (label, value) in enumerate(judgements[:4]):
        x = 630 + judge_index * judge_width
        judge_parts.append(text(x, y + 36, label, 8, fill="#697681"))
        judge_parts.append(text(x, y + 57, number(value), 12, fill="#101824", weight=700))
    client = str(play.get("score_version") or "")
    client_label = "Lazer" if client == "lazer" else "Stable"
    return f"""
<g opacity="{opacity}"><rect x="30" y="{y}" width="1340" height="92" fill="{fill}" stroke="{"#f1a7c8" if best else "#d4d5d2"}"/><rect x="30" y="{y}" width="4" height="92" fill="{PINK if best else CYAN if index % 3 == 0 else "#bec6c9"}"/>
{text(57, y + 55, str(play["index"]).zfill(2), 13, fill="#66717a", anchor="middle", weight=700)}
{text(112, y + 63, grade, 49, fill=grade_color, anchor="middle", weight=700)}
{text(158, y + 55, number(play["score"]), 16, fill="#101824", weight=700)}
{text(305, y + 55, number(play["pp"], 2), 17, fill="#e63d83", weight=700)}
{text(421, y + 55, number(play["accuracy"], 2) + "%", 17, fill="#168f9b", weight=700)}
{text(525, y + 55, number(play["combo"]) + "x", 17, fill="#101824", weight=700)}
{"".join(judge_parts)}
{mod_strip(play["mods"], play.get("speed_changes") or {}, x=942, y=y + 27, icon_size=38, max_width=174, preserve_artwork_ratio=True)}
<rect x="1135" y="{y + 30}" width="84" height="31" rx="16" fill="#060a0d"/>
{text(1177, y + 51, "★ " + number(play["stars"], 2), 13, fill="#ffd966", anchor="middle", weight=700)}
{text(1350, y + 38, play["date"], 12, fill="#101824", anchor="end", weight=700)}
{text(1350, y + 63, client_label if client else "", 9, fill="#168f9b" if client == "lazer" else "#101824", anchor="end", weight=700)}</g>
{f'<rect x="1285" y="{y - 8}" width="70" height="16" rx="8" fill="{PINK}"/>{text(1320, y + 3, "BEST SCORE", 8, anchor="middle", weight=700)}' if best else ""}
"""


def build_score_history_svg(data: dict) -> tuple[str, int]:
    plays = data["plays"]
    footer_y = 315 + len(plays) * 102
    height = footer_y + 58
    rows = "".join(_row(play, index) for index, play in enumerate(plays))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
<defs><pattern id="history-dots" width="17" height="17" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#26303a" opacity=".06"/></pattern></defs><rect width="{WIDTH}" height="{height}" fill="#f5f1e9"/><rect y="250" width="{WIDTH}" height="{height - 250}" fill="url(#history-dots)"/>
{_header(data)}{_columns()}{rows}
{fitted_text(33, footer_y + 31, "说明：" + data["disclaimer"], 9, 860, fill="#101824")}
{text(1367, footer_y + 31, "生成于 " + data["generated_at"], 9, fill="#101824", anchor="end")}</svg>"""
    return svg, height


async def render_score_history_svg(data: dict):
    svg, height = build_score_history_svg(data)
    return await render_svg_jpeg_async(svg, width=WIDTH, height=height, quality=92)
