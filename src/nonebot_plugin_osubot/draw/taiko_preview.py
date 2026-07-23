import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from .static import Torus_Regular_8, Torus_Regular_15

HIT_DON = 0x00
HIT_KAT = 0x01
BIG_DON = 0x02
BIG_KAT = 0x03
SLIDER_START = 0x04
SLIDER_END = 0x05
BLIDER_START = 0x06
BLIDER_END = 0x07
SPINNER_START = 0x08
SPINNER_END = 0x09
TIME_TOL = 5  # 5 ms of tolerance
FLOAT_TOL = 0.00001

LEFT_MARGIN = 25
FIELD_HEIGHT = 30
FIELD_DISTANCE = 65

HIT_RADIUS = 8
BIG_RADIUS = 13

BEAT_WIDTH = int(0.92 * HIT_RADIUS * 2 * 4)
IMAGE_WIDTH = 1110


def _map_to_image_legacy(map_data) -> BytesIO:
    Image.MAX_IMAGE_PIXELS = None
    img = Image.new(mode="RGB", size=(3000, 30000), color=0x121212)
    draw = ImageDraw.Draw(img)

    # title_font = Torus_Regular_30
    # semi_font = Torus_Regular_25
    # reg_font = Torus_Regular_20
    small_font = Torus_Regular_15
    tiny_font = Torus_Regular_8

    # draw.text(
    #     (LEFT_MARGIN, 40),
    #     map_data.artist + " - " + map_data.title + " [" + map_data.diff + "]",
    #     font=title_font,
    #     fill="#FFF",
    # )
    # draw.text((LEFT_MARGIN, 90), "by " + map_data.creator, font=semi_font, fill="#CCC")
    # draw.text((LEFT_MARGIN, 135), "HP = " + str(map_data.hp) +
    # " OD = " + str(map_data.od), font=reg_font, fill="#AAA")

    max_meter = 0
    timing_sections = []  # (start, beat_ms, meter, [list of hit_object])
    separating_times = []

    for timing_point in map_data.timing_points:
        separating_times.append(timing_point[0])
    separating_times.append(10**10)

    for i in range(len(separating_times) - 1):
        current_list = []
        for hit_object in map_data.hit_objects:
            if separating_times[i] - TIME_TOL <= hit_object[0] < separating_times[i + 1] - TIME_TOL:
                current_list.append(hit_object)
        timing_sections.append(
            (map_data.timing_points[i][0], map_data.timing_points[i][1], map_data.timing_points[i][2], current_list)
        )

    y_start = 40
    max_x = 0
    max_y = 0
    bar_number = 1

    for i in range(len(timing_sections)):
        if not timing_sections[i][3]:
            continue
        if i == len(timing_sections) - 1:
            duration = timing_sections[i][3][-1][0] - timing_sections[i][0]
        else:
            duration = timing_sections[i + 1][0] - timing_sections[i][0]

        meter = map_data.timing_points[i][2]
        max_meter = max(meter, max_meter)
        beat_length = map_data.timing_points[i][1]
        bar_length = beat_length * meter
        phrase_length = bar_length * 4

        rect_count = math.ceil((duration - TIME_TOL) / phrase_length)
        last_rect_width = math.ceil((duration - (rect_count - 1) * phrase_length - TIME_TOL) / beat_length) * BEAT_WIDTH
        y = y_start

        bpm = round(1 / timing_sections[i][1] * 60000, 1)
        if str(bpm).split(".")[-1] == "0":
            bpm = int(bpm)

        draw.text((LEFT_MARGIN + 5, y - 25), "BPM " + str(bpm), font=tiny_font, fill="#21F")

        for count in range(rect_count):
            x = 25
            if count == rect_count - 1:
                draw.rectangle(
                    [(LEFT_MARGIN, y), (LEFT_MARGIN + last_rect_width, y + FIELD_HEIGHT)],
                    width=2,
                    fill="#666",
                    outline="#AAA",
                )
            else:
                draw.rectangle(
                    [(LEFT_MARGIN, y), (LEFT_MARGIN + BEAT_WIDTH * 4 * meter, y + FIELD_HEIGHT)],
                    width=2,
                    fill="#666",
                    outline="#AAA",
                )

            for beat in range(4 * meter + 1):
                if count == rect_count - 1:
                    if (rect_count - 1) * phrase_length + beat * beat_length - TIME_TOL > duration:
                        break
                if beat % meter == 0:
                    draw.line([(x, y - 20), (x, y + FIELD_HEIGHT)], width=2, fill="#DDD")
                    if beat != 4 * meter and not (count == rect_count - 1 and x >= last_rect_width):
                        draw.text((x + 5, y - 15), str(bar_number), font=tiny_font, fill="#F02")
                        bar_number += 1
                    max_x = max(max_x, x)
                else:
                    draw.line([(x, y), (x, y + FIELD_HEIGHT)], width=1, fill="#AAA")
                x += BEAT_WIDTH
            y += FIELD_DISTANCE

        reversed_order_objects = timing_sections[i][3]
        reversed_order_objects.reverse()
        for hit_object in reversed_order_objects:
            time_diff = hit_object[0] - timing_sections[i][0]

            line_index = (time_diff + TIME_TOL) // phrase_length
            hori_pos = int(((time_diff - line_index * phrase_length) / phrase_length) * (BEAT_WIDTH * 4 * meter))
            vert_pos = y_start + line_index * FIELD_DISTANCE + FIELD_HEIGHT // 2
            max_y = max(max_y, vert_pos)
            center = (hori_pos + 1 + LEFT_MARGIN, vert_pos)

            if hit_object[1] == HIT_DON:
                draw.ellipse(
                    (center[0] - HIT_RADIUS, center[1] - HIT_RADIUS, center[0] + HIT_RADIUS, center[1] + HIT_RADIUS),
                    width=2,
                    fill="#EB452C",
                    outline="#FFF",
                )
            elif hit_object[1] == HIT_KAT:
                draw.ellipse(
                    (center[0] - HIT_RADIUS, center[1] - HIT_RADIUS, center[0] + HIT_RADIUS, center[1] + HIT_RADIUS),
                    width=2,
                    fill="#448DAB",
                    outline="#FFF",
                )
            elif hit_object[1] == BIG_DON:
                draw.ellipse(
                    (center[0] - BIG_RADIUS, center[1] - BIG_RADIUS, center[0] + BIG_RADIUS, center[1] + BIG_RADIUS),
                    width=2,
                    fill="#EB452C",
                    outline="#FFF",
                )
            elif hit_object[1] == BIG_KAT:
                draw.ellipse(
                    (center[0] - BIG_RADIUS, center[1] - BIG_RADIUS, center[0] + BIG_RADIUS, center[1] + BIG_RADIUS),
                    width=2,
                    fill="#448DAB",
                    outline="#FFF",
                )
            elif hit_object[1] == SLIDER_START:
                draw.ellipse(
                    (center[0] - HIT_RADIUS, center[1] - HIT_RADIUS, center[0] + HIT_RADIUS, center[1] + HIT_RADIUS),
                    width=2,
                    fill="#FCB706",
                    outline="#FFF",
                )
            elif hit_object[1] == BLIDER_START:
                draw.ellipse(
                    (center[0] - BIG_RADIUS, center[1] - BIG_RADIUS, center[0] + BIG_RADIUS, center[1] + BIG_RADIUS),
                    width=2,
                    fill="#FCB706",
                    outline="#FFF",
                )
            elif hit_object[1] == SPINNER_START:
                draw.ellipse(
                    (
                        center[0] - (BIG_RADIUS - 4),
                        center[1] - (BIG_RADIUS - 4),
                        center[0] + (BIG_RADIUS - 4),
                        center[1] + (BIG_RADIUS - 4),
                    ),
                    width=2,
                    fill="#333",
                    outline="#FFF",
                )
                draw.ellipse(
                    (
                        center[0] - (HIT_RADIUS - 4),
                        center[1] - (HIT_RADIUS - 4),
                        center[0] + (HIT_RADIUS - 4),
                        center[1] + (HIT_RADIUS - 4),
                    ),
                    width=2,
                    fill="#333",
                    outline="#FFF",
                )

        y_start += rect_count * FIELD_DISTANCE

    new_width = max_x + LEFT_MARGIN
    new_height = max_y + 65
    draw.text(
        (new_width - 400, new_height - 30),
        "Original Generated by Tacobo bot (Tacobo#4715) - OoO#0997",
        font=small_font,
        fill="#AAA",
    )

    img = img.crop((0, 0, new_width, new_height))
    byt = BytesIO()
    img.save(byt, format="PNG")
    return byt


PREVIEW_BACKGROUND = "#0a1017"
PREVIEW_TRACK = "#0e1720"
PREVIEW_LINE = "#283744"
PREVIEW_STRONG_LINE = "#71818d"
PREVIEW_MUTED = "#677783"
PREVIEW_DON = "#e65d69"
PREVIEW_KAT = "#579bb4"
PREVIEW_ACCENT = "#c2aa69"
PREVIEW_OUTLINE = "#dce4e9"


def _draw_preview_note(draw: ImageDraw.ImageDraw, x: int, y: int, kind: int) -> None:
    if kind in (HIT_DON, HIT_KAT, BIG_DON, BIG_KAT):
        color = PREVIEW_DON if kind in (HIT_DON, BIG_DON) else PREVIEW_KAT
        radius = 7 if kind in (HIT_DON, HIT_KAT) else 11
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=color,
            outline=PREVIEW_OUTLINE,
            width=1,
        )
    elif kind in (SLIDER_START, BLIDER_START):
        radius = 7 if kind == SLIDER_START else 10
        draw.rounded_rectangle(
            (x - radius, y - 5, x + radius, y + 5),
            radius=4,
            fill=PREVIEW_ACCENT,
        )
    elif kind == SPINNER_START:
        draw.ellipse(
            (x - 10, y - 10, x + 10, y + 10),
            outline=PREVIEW_MUTED,
            width=2,
        )
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=PREVIEW_MUTED)


def map_to_image(map_data) -> BytesIO:
    timing_sections = []
    separating_times = [point[0] for point in map_data.timing_points]
    separating_times.append(10**10)

    for index, point in enumerate(map_data.timing_points):
        objects = [
            item
            for item in map_data.hit_objects
            if separating_times[index] - TIME_TOL <= item[0] < separating_times[index + 1] - TIME_TOL
        ]
        if objects:
            timing_sections.append((*point, objects))

    if not timing_sections:
        image = Image.new("RGB", (IMAGE_WIDTH, 120), PREVIEW_BACKGROUND)
        draw = ImageDraw.Draw(image)
        draw.text((LEFT_MARGIN, 45), "No taiko objects", font=Torus_Regular_15, fill=PREVIEW_MUTED)
        result = BytesIO()
        image.save(result, "PNG")
        return result

    layouts = []
    max_meter = max(section[2] for section in timing_sections)
    for index, (start, beat_length, meter, objects) in enumerate(timing_sections):
        end = objects[-1][0] if index == len(timing_sections) - 1 else timing_sections[index + 1][0]
        duration = max(beat_length, end - start)
        phrase_length = beat_length * meter * 4
        row_count = max(1, math.ceil((duration - TIME_TOL) / phrase_length))
        layouts.append((start, beat_length, meter, objects, duration, phrase_length, row_count))

    row_distance = 58
    section_gap = 16
    image_width = LEFT_MARGIN * 2 + BEAT_WIDTH * 4 * max_meter
    image_height = 28 + sum(layout[-1] * row_distance + section_gap for layout in layouts) + 38
    image = Image.new("RGB", (image_width, image_height), PREVIEW_BACKGROUND)
    draw = ImageDraw.Draw(image)

    section_y = 28
    bar_number = 1
    for start, beat_length, meter, objects, duration, phrase_length, row_count in layouts:
        bpm = 60000 / beat_length
        draw.text(
            (LEFT_MARGIN + 2, section_y - 25),
            f"BPM{bpm:g}",
            font=Torus_Regular_8,
            fill=PREVIEW_MUTED,
        )

        full_track_width = BEAT_WIDTH * 4 * meter
        for row in range(row_count):
            y = section_y + row * row_distance
            if row == row_count - 1:
                remaining = max(beat_length, duration - row * phrase_length)
                beat_count = min(meter * 4, max(1, math.ceil((remaining - TIME_TOL) / beat_length)))
            else:
                beat_count = meter * 4
            track_width = beat_count * BEAT_WIDTH

            draw.rectangle(
                (LEFT_MARGIN, y, LEFT_MARGIN + track_width, y + FIELD_HEIGHT),
                fill=PREVIEW_TRACK,
            )
            draw.line(
                (
                    LEFT_MARGIN,
                    y + FIELD_HEIGHT // 2,
                    LEFT_MARGIN + track_width,
                    y + FIELD_HEIGHT // 2,
                ),
                fill="#22313c",
            )
            for beat in range(beat_count + 1):
                x = LEFT_MARGIN + beat * BEAT_WIDTH
                is_bar = beat % meter == 0
                draw.line(
                    (x, y - (7 if is_bar else 0), x, y + FIELD_HEIGHT),
                    fill=PREVIEW_STRONG_LINE if is_bar else PREVIEW_LINE,
                    width=2 if is_bar else 1,
                )
                if is_bar and beat < beat_count:
                    draw.text(
                        (x + 4, y - 13),
                        str(bar_number),
                        font=Torus_Regular_8,
                        fill=PREVIEW_MUTED,
                    )
                    bar_number += 1

        for timestamp, kind in objects:
            time_difference = timestamp - start
            row = min(int((time_difference + TIME_TOL) // phrase_length), row_count - 1)
            within_phrase = time_difference - row * phrase_length
            x = LEFT_MARGIN + int(within_phrase / phrase_length * full_track_width)
            y = section_y + row * row_distance + FIELD_HEIGHT // 2
            _draw_preview_note(draw, x, y, kind)

        section_y += row_count * row_distance + section_gap

    footer = f"{map_data.artist} — {map_data.title} [{map_data.diff}] · OSUBOT FULL MAP"
    draw.text((LEFT_MARGIN, image.height - 25), footer, font=Torus_Regular_15, fill="#445560")
    result = BytesIO()
    image.save(result, "PNG")
    return result


class MapData:
    def __init__(
        self, title, artist, creator, diff, hp, od, timing_points, hit_objects
    ):  # timing_points: list of (time, beat_length, meter), hit_objects: list of (time, type)
        self.title = title
        self.artist = artist
        self.creator = creator
        self.diff = diff
        self.hp = hp
        self.od = od
        self.timing_points = timing_points
        self.hit_objects = hit_objects


def parse_map(map_path: Path):
    map_data = MapData(None, None, None, None, None, None, [], [])
    with open(map_path, encoding="utf-8") as f:
        while True:
            line = f.readline().strip()
            if line[: min(6, len(line))] == "Title:":
                map_data.title = line[6:]
            elif line[: min(7, len(line))] == "Artist:":
                map_data.artist = line[7:]
            elif line[: min(8, len(line))] == "Creator:":
                map_data.creator = line[8:]
            elif line[: min(8, len(line))] == "Version:":
                map_data.diff = line[8:]
            elif line[: min(12, len(line))] == "HPDrainRate:":
                map_data.hp = float(line[12:])
            elif line[: min(18, len(line))] == "OverallDifficulty:":
                map_data.od = float(line[18:])
            elif line == "[TimingPoints]":
                break

        while True:  # time,beatLength,meter,sampleSet,sampleIndex,volume,uninherited,effects
            line = f.readline().strip()
            if line == "[HitObjects]":
                break
            if line == "":
                continue
            parts = line.split(",")
            if len(parts) < 7:
                continue

            try:
                val_list = list(map(float, parts))
            except ValueError:
                continue
            if val_list[6] == 1:
                map_data.timing_points.append((int(val_list[0]), val_list[1], int(val_list[2])))

        while True:  # x,y,time,type,hitsound,objectParams,hitSample
            line = f.readline().strip()
            if line == "":
                break

            val_list = list(map(int, line.split(",")[:5]))
            time = val_list[2]

            if val_list[3] & (1 << 0):  # hitcircles
                if val_list[4] & (1 << 1) or val_list[4] & (1 << 3):
                    if val_list[4] & (1 << 2):
                        obj_type = BIG_KAT
                    else:
                        obj_type = HIT_KAT
                else:
                    if val_list[4] & (1 << 2):
                        obj_type = BIG_DON
                    else:
                        obj_type = HIT_DON
                map_data.hit_objects.append((time, obj_type))

            elif val_list[3] & (1 << 3):  # spinners
                time_start = val_list[2]
                map_data.hit_objects.append((time_start, SPINNER_START))
                # map_data.hit_objects.append((time_end, SPINNER_END))
            elif val_list[3] & (1 << 1):  # sliders
                time = val_list[2]
                # length = val_list[7]
                if val_list[4] & (1 << 2):
                    map_data.hit_objects.append((time, BLIDER_START))
                    # map_data.hit_objects.append((time + length, BLIDER_END))
                else:
                    map_data.hit_objects.append((time, SLIDER_START))
                    # map_data.hit_objects.append((time + length, SLIDER_END))
    return map_data
