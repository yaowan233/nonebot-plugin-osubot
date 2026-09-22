import argparse
import asyncio
import json
from pathlib import Path

import nonebot


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--username", default="yaowan233")
    parser.add_argument("--player-id", type=int, default=3162675)
    args = parser.parse_args()
    nonebot.init(log_level="WARNING")
    from nonebot_plugin_osubot.draw.recommend import draw_recommend
    from nonebot_plugin_osubot.recommendation import prediction_display
    from nonebot_plugin_osubot.schema.alphaosu import RecommendData

    raw = json.loads(args.source.read_text(encoding="utf-8"))
    mode = raw.get("mode") or raw["applied_request"]["mode"]
    items = [
        {
            "map_id": item["beatmap_id"], "mod": item.get("mod_int", 0), "mod_str": item["mods"],
            "stars": item["stars"], "final_score": item["ranking_score"],
            "title": f"{item['title']} [{item['version']}]", "beatmapset_id": item["beatmapset_id"],
            **prediction_display(item, mode),
        }
        for item in raw["items"][:10]
    ]
    data = RecommendData(player_id=args.player_id, mode=mode, target="balanced", recommendations=items)
    result = await draw_recommend(data, args.username, f"https://a.ppy.sh/{args.player_id}")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_bytes(result)
    print(args.destination)


if __name__ == "__main__":
    asyncio.run(main())
