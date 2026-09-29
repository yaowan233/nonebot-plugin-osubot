"""Standalone native renderer worker; run by file path to avoid loading NoneBot."""

import json
import sys

from osu_beatmap_preview import generate_preview


if __name__ == "__main__":
    request = json.load(sys.stdin)
    result = generate_preview(**request)
    print(json.dumps(result))
