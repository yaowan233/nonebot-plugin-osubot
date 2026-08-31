from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock

import pytest


def test_play_mode_uses_one_canonical_representation():
    from nonebot_plugin_osubot.server import ModeVariant, PlayMode, Ruleset

    assert PlayMode.parse("std") == PlayMode(Ruleset.OSU)
    assert PlayMode.parse("5") == PlayMode(Ruleset.TAIKO, ModeVariant.RELAX)
    assert PlayMode.parse("ap") == PlayMode(Ruleset.OSU, ModeVariant.AUTOPILOT)
    assert PlayMode.parse("rxmania") is None
    assert PlayMode.parse("8").legacy_id == 8
    assert PlayMode.parse("6").key == "rxfruits"


@pytest.mark.parametrize(
    ("requested", "native_ruleset", "expected"),
    [("4", 1, "5"), ("6", 1, "5"), ("4", 2, "6"), ("5", 2, "6"), ("8", 1, "1")],
)
def test_play_mode_converts_private_modes_for_native_map(requested: str, native_ruleset: int, expected: str):
    from nonebot_plugin_osubot.server import PlayMode

    assert PlayMode.parse(requested).for_native_ruleset(native_ruleset).legacy_key == expected


def test_registered_servers_expose_aliases_modes_and_capabilities():
    from nonebot_plugin_osubot.api import get_server
    from nonebot_plugin_osubot.server import ModeVariant, PlayMode, Ruleset, ServerFeature

    official = get_server("osu")
    ppysb = get_server("sb")
    g0v0 = get_server("gu")

    assert official.id == "osu"
    assert ppysb.id == "ppysb"
    assert g0v0.id == "g0v0"
    assert official.supports(ServerFeature.BP_FIX, PlayMode(Ruleset.OSU))
    assert ppysb.supports(ServerFeature.BP_FIX, PlayMode(Ruleset.OSU))
    assert g0v0.supports(ServerFeature.BP_FIX, PlayMode(Ruleset.OSU))
    assert not ppysb.supports(ServerFeature.BP_FIX, PlayMode(Ruleset.OSU, ModeVariant.RELAX))
    assert not g0v0.supports(ServerFeature.BP_FIX, PlayMode(Ruleset.OSU, ModeVariant.RELAX))
    assert not ppysb.supports(ServerFeature.PP_HISTORY, PlayMode(Ruleset.OSU))
    assert g0v0.supports_mode(PlayMode(Ruleset.OSU, ModeVariant.RELAX))
    assert not official.supports_mode(PlayMode(Ruleset.OSU, ModeVariant.RELAX))
    assert ppysb.descriptor.profile_url(42) == "https://akatsuki.gg/u/42"
    assert g0v0.descriptor.profile_url(42) == "https://lazer.g0v0.top/users/42"


def test_binding_specs_are_selected_through_server_aliases():
    from nonebot_plugin_osubot.bindings import get_binding_spec

    official = get_binding_spec("official")
    ppysb = get_binding_spec("sb")
    g0v0 = get_binding_spec("gu")

    assert official.bind_command == "/bind"
    assert ppysb.bind_command == "/sbbind"
    assert ppysb.stores_default_mode
    assert g0v0.bind_command == "/gubind"
    assert g0v0.stores_default_mode


@pytest.mark.asyncio
async def test_legacy_api_facades_delegate_to_registered_server(monkeypatch):
    from nonebot_plugin_osubot import api
    from nonebot_plugin_osubot.server import (
        GameServer,
        MapScoreQuery,
        MapScores,
        ModeVariant,
        PlayMode,
        Ruleset,
        ServerCapabilities,
        ServerDescriptor,
        ServerFeature,
        ServerRegistry,
        UserScoreQuery,
    )

    class FakeServer(GameServer):
        descriptor = ServerDescriptor(
            id="fake",
            label="Fake",
            aliases=frozenset({"f"}),
            modes=frozenset({PlayMode(Ruleset.OSU, ModeVariant.RELAX)}),
            capabilities=ServerCapabilities.all(ServerFeature.USER_INFO, ServerFeature.USER_SCORES),
        )

        def __init__(self):
            self.score_query = None
            self.map_query = None

        async def resolve_user(self, identifier: str) -> int:
            assert identifier == "player"
            return 42

        async def get_user(self, user_id: int | str, mode: PlayMode):
            assert (user_id, mode.legacy_key) == (42, "4")
            return SimpleNamespace(id=42)

        async def get_scores(self, query: UserScoreQuery):
            self.score_query = query
            return [SimpleNamespace(id=1)]

        async def get_map_scores(self, query: MapScoreQuery) -> MapScores:
            self.map_query = query
            return MapScores(scores=[SimpleNamespace(id=2)], origin="remote", complete=True)

    fake = FakeServer()
    registry = ServerRegistry([fake])
    monkeypatch.setattr(api, "server_registry", registry)

    assert await api.get_uid_by_name("player", "f") == 42
    assert (await api.get_user_info_data(42, "rxosu", "fake")).id == 42
    scores = await api.get_user_scores(
        42,
        "4",
        "best",
        source="fake",
        legacy_only=True,
        include_failed=False,
        offset=3,
        limit=5,
    )
    assert scores[0].id == 1
    assert fake.score_query == UserScoreQuery(
        user_id=42,
        mode=PlayMode(Ruleset.OSU, ModeVariant.RELAX),
        scope="best",
        legacy_only=True,
        include_failed=False,
        offset=3,
        limit=5,
    )

    map_data = {"id": 123, "checksum": "abc"}
    lookup = await api.get_map_scores(42, "4", map_data, source="fake", legacy_only=True)
    assert lookup.scores[0].id == 2
    assert fake.map_query == MapScoreQuery(
        user_id=42,
        mode=PlayMode(Ruleset.OSU, ModeVariant.RELAX),
        beatmap=map_data,
        legacy_only=True,
    )


@pytest.mark.asyncio
async def test_ppysb_adapter_hides_remote_offset_pagination(monkeypatch):
    from nonebot_plugin_osubot import api

    def make_score(index: int):
        return SimpleNamespace(
            mods=0,
            mode=0,
            grade="A",
            acc=98.0,
            score=index,
            play_time="2026-01-01T00:00:00",
            max_combo=100,
            pp=100.0,
            nmiss=0,
            ngeki=0,
            nkatu=0,
            n50=0,
            n100=0,
            n300=100,
            beatmap=SimpleNamespace(
                id=index,
                set_id=1,
                artist="artist",
                title="title",
                version="version",
                creator="mapper",
                total_length=100,
                mode=0,
                bpm=180,
                cs=4,
                ar=9,
                hp=6,
                od=8,
                diff=5,
                md5="checksum",
            ),
        )

    async def fake_request(url: str, _headers: dict, _message: str):
        assert parse_qs(urlparse(url).query)["limit"] == ["30"]
        return {}

    monkeypatch.setattr(api, "make_request", fake_request)
    monkeypatch.setattr(
        api,
        "ScoresResponse",
        lambda **_data: SimpleNamespace(scores=[make_score(index) for index in range(30)]),
    )

    scores = await api._get_ppysb_user_scores(42, "osu", offset=10, limit=20)

    assert [score.total_score for score in scores] == list(range(10, 30))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("offset", "limit"),
    [
        (0, 0),
        (0, -1),
        (-1, 20),
        (100, 1),
        (120, 20),
    ],
)
async def test_ppysb_adapter_skips_unreachable_score_pages(monkeypatch, offset, limit):
    from nonebot_plugin_osubot import api

    request = AsyncMock()
    monkeypatch.setattr(api, "make_request", request)

    assert await api._get_ppysb_user_scores(42, "osu", offset=offset, limit=limit) == []
    request.assert_not_awaited()
