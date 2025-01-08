import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from .static import Torus_Regular_8, Torus_Regular_15, Torus_Regular_20, Torus_Regular_25, Torus_Regular_30

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


def map_to_image(map_data) -> BytesIO:
    Image.MAX_IMAGE_PIXELS = None
    img = Image.new(mode="RGB", size=(3000, 30000), color=0x121212)
    draw = ImageDraw.Draw(img)

    title_font = Torus_Regular_30
    semi_font = Torus_Regular_25
    reg_font = Torus_Regular_20
    small_font = Torus_Regular_15
    tiny_font = Torus_Regular_8

    draw.text(
        (LEFT_MARGIN, 40),
        map_data.artist + " - " + map_data.title + " [" + map_data.diff + "]",
        font=title_font,
        fill="#FFF",
    )
    draw.text((LEFT_MARGIN, 90), "by " + map_data.creator, font=semi_font, fill="#CCC")
    draw.text((LEFT_MARGIN, 135), "HP = " + str(map_data.hp) + " OD = " + str(map_data.od), font=reg_font, fill="#AAA")

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

    y_start = 200
    max_x = 0
    max_y = 0
    bar_number = 1

    for i in range(len(timing_sections)):
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
            elif not line[0].isdigit():
                continue

            val_list = list(map(float, line.split(",")))
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
