def make_players(count: int) -> list[dict]:
    return [
        {
            "osu_id": index,
            "osu_name": f"player-{index}",
            "qq_name": f"qq-{index}",
            "avatar_url": "",
            "pp": 20_000 - index,
            "global_rank": index,
            "delta": float(index),
        }
        for index in range(1, count + 1)
    ]


def test_rank_display_pins_requester_below_top_20():
    from nonebot_plugin_osubot.draw.rank import prepare_rank_display

    data = prepare_rank_display(make_players(100), requester_osu_id=76)

    assert data["total_count"] == 100
    assert [player["place"] for player in data["podium"]] == [2, 1, 3]
    assert len(data["visible"]) == 20
    assert data["pinned"]["place"] == 76
    assert data["hidden_end"] == 75


def test_rank_display_does_not_duplicate_visible_requester():
    from nonebot_plugin_osubot.draw.rank import prepare_rank_display

    data = prepare_rank_display(make_players(30), requester_osu_id=6)

    assert data["pinned"] is None
    assert sum(player["is_self"] for player in data["visible"]) == 1


def test_rank_display_excludes_players_below_threshold():
    from nonebot_plugin_osubot.draw.rank import prepare_rank_display

    players = make_players(3)
    players[-1]["pp"] = 99

    data = prepare_rank_display(players, requester_osu_id=3)

    assert data["total_count"] == 2
    assert data["pinned"] is None
