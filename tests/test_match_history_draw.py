from types import SimpleNamespace


def test_prepare_match_data_builds_team_scoreboard_and_normalizes_mods():
    from nonebot_plugin_osubot.draw.match_history import prepare_match_data

    users = [
        SimpleNamespace(id=1, username="RedPlayer", avatar_url="red.png"),
        SimpleNamespace(id=2, username="BluePlayer", avatar_url="blue.png"),
    ]
    beatmapset = SimpleNamespace(title="Test Map", creator="Mapper", covers=SimpleNamespace(cover="cover.jpg"))
    beatmap = SimpleNamespace(
        beatmapset=beatmapset,
        version="Insane",
        difficulty_rating=6.42,
        beatmapset_id=100,
    )
    scores = [
        SimpleNamespace(
            user_id=1,
            score=1_000_000,
            accuracy=0.99,
            max_combo=1000,
            mods=["NC", "HD", "CL"],
            match={"team": "red"},
        ),
        SimpleNamespace(
            user_id=2,
            score=900_000,
            accuracy=0.98,
            max_combo=900,
            mods=[],
            match={"team": "blue"},
        ),
    ]
    game = SimpleNamespace(
        team_type="team-vs",
        beatmap=beatmap,
        beatmap_id=200,
        mods=["DT"],
        scores=scores,
    )
    match = SimpleNamespace(
        match={
            "name": "Cup: (Red Team) vs (Blue Team)",
            "start_time": "2026-07-22T10:00:00+00:00",
            "end_time": "2026-07-22T11:30:00+00:00",
        },
        events=[SimpleNamespace(detail=SimpleNamespace(type="other"), game=game)],
        users=users,
    )

    data = prepare_match_data(match, "123")

    assert data["is_team"] is True
    assert data["red_name"] == "Red Team"
    assert data["blue_name"] == "Blue Team"
    assert (data["red_wins"], data["blue_wins"]) == (1, 0)
    assert data["duration"] == "1h 30m"
    assert data["games"][0]["winner"] == "red"
    assert data["games"][0]["red_players"][0]["mods"] == ["NC", "HD"]
