from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Literal

from .schema.score import UnifiedScore
from .schema.user import UnifiedUser


class Ruleset(IntEnum):
    OSU = 0
    TAIKO = 1
    FRUITS = 2
    MANIA = 3


class ModeVariant(str, Enum):
    STANDARD = "standard"
    RELAX = "relax"
    AUTOPILOT = "autopilot"


class RelaxEncoding(str, Enum):
    NONE = "none"
    RULESET_ID = "ruleset_id"
    MOD = "mod"


_MODE_BY_ID = {
    0: (Ruleset.OSU, ModeVariant.STANDARD, "osu"),
    1: (Ruleset.TAIKO, ModeVariant.STANDARD, "taiko"),
    2: (Ruleset.FRUITS, ModeVariant.STANDARD, "fruits"),
    3: (Ruleset.MANIA, ModeVariant.STANDARD, "mania"),
    4: (Ruleset.OSU, ModeVariant.RELAX, "rxosu"),
    5: (Ruleset.TAIKO, ModeVariant.RELAX, "rxtaiko"),
    6: (Ruleset.FRUITS, ModeVariant.RELAX, "rxfruits"),
    8: (Ruleset.OSU, ModeVariant.AUTOPILOT, "aposu"),
}
_ID_BY_MODE = {(ruleset, variant): mode_id for mode_id, (ruleset, variant, _key) in _MODE_BY_ID.items()}
_KEY_BY_MODE = {(ruleset, variant): key for _mode_id, (ruleset, variant, key) in _MODE_BY_ID.items()}
_MODE_ALIASES = {
    "0": 0,
    "osu": 0,
    "osu!": 0,
    "o": 0,
    "std": 0,
    "standard": 0,
    "1": 1,
    "taiko": 1,
    "t": 1,
    "tk": 1,
    "2": 2,
    "catch": 2,
    "c": 2,
    "ctb": 2,
    "fruits": 2,
    "3": 3,
    "mania": 3,
    "m": 3,
    "4": 4,
    "rx": 4,
    "rxstd": 4,
    "rxosu": 4,
    "5": 5,
    "rxtaiko": 5,
    "rxtk": 5,
    "6": 6,
    "rxcatch": 6,
    "rxctb": 6,
    "rxfruits": 6,
    "8": 8,
    "ap": 8,
    "apstd": 8,
    "aposu": 8,
}


@dataclass(frozen=True, slots=True)
class PlayMode:
    ruleset: Ruleset
    variant: ModeVariant = ModeVariant.STANDARD

    def __post_init__(self):
        if (self.ruleset, self.variant) not in _ID_BY_MODE:
            raise ValueError(f"不支持的模式组合: {self.ruleset.name}/{self.variant.value}")

    @property
    def legacy_id(self) -> int:
        return _ID_BY_MODE[(self.ruleset, self.variant)]

    @property
    def legacy_key(self) -> str:
        return str(self.legacy_id)

    @property
    def key(self) -> str:
        return _KEY_BY_MODE[(self.ruleset, self.variant)]

    @classmethod
    def parse(cls, value: int | str | PlayMode) -> PlayMode | None:
        if isinstance(value, PlayMode):
            return value
        mode_id = _MODE_ALIASES.get(str(value).strip().lower())
        if mode_id is None:
            return None
        ruleset, variant, _key = _MODE_BY_ID[mode_id]
        return cls(ruleset, variant)

    def for_native_ruleset(self, native_ruleset: int | Ruleset) -> PlayMode:
        native = Ruleset(int(native_ruleset))
        if native == Ruleset.OSU:
            return self
        if self.variant == ModeVariant.RELAX and native in {Ruleset.TAIKO, Ruleset.FRUITS}:
            return PlayMode(native, ModeVariant.RELAX)
        return PlayMode(native)


STANDARD_MODES = frozenset(PlayMode(ruleset) for ruleset in Ruleset)
PRIVATE_MODES = frozenset(PlayMode(ruleset, variant) for ruleset, variant, _key in _MODE_BY_ID.values())


class ServerFeature(str, Enum):
    USER_INFO = "user_info"
    USER_SCORES = "user_scores"
    MAP_SCORES = "map_scores"
    FIRST_SCORE = "first_score"
    PP_HISTORY = "pp_history"
    BP_FIX = "bp_fix"
    OFFICIAL_SNAPSHOTS = "official_snapshots"
    SCORE_VERSION = "score_version"
    LEGACY_SCORE_RULES = "legacy_score_rules"
    SERVER_REPORTED_PP = "server_reported_pp"


@dataclass(frozen=True, slots=True)
class ServerCapabilities:
    """Modes supported by each feature; ``None`` means every server mode."""

    feature_modes: Mapping[ServerFeature, frozenset[PlayMode] | None] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "feature_modes", MappingProxyType(dict(self.feature_modes)))

    @classmethod
    def all(cls, *features: ServerFeature) -> ServerCapabilities:
        return cls(dict.fromkeys(features))

    def supports(self, feature: ServerFeature, mode: PlayMode | None, server_modes: frozenset[PlayMode]) -> bool:
        if feature not in self.feature_modes:
            return False
        if mode is None:
            return True
        allowed_modes = self.feature_modes[feature]
        return mode in server_modes and (allowed_modes is None or mode in allowed_modes)


@dataclass(frozen=True, slots=True)
class ServerDescriptor:
    id: str
    label: str
    aliases: frozenset[str]
    modes: frozenset[PlayMode]
    capabilities: ServerCapabilities
    avatar_base_url: str = "https://a.ppy.sh"
    profile_url_template: str = "https://osu.ppy.sh/users/{user_id}"
    relax_encoding: RelaxEncoding = RelaxEncoding.NONE
    default_score_version: Literal["stable", "lazer"] = "lazer"

    def supports(self, feature: ServerFeature, mode: PlayMode | None = None) -> bool:
        return self.capabilities.supports(feature, mode, self.modes)

    def profile_url(self, user_id: int | str) -> str:
        return self.profile_url_template.format(user_id=user_id)

    def score_uses_lazer(self, score_version: str | None, requested_lazer: bool) -> bool:
        if score_version in {"stable", "lazer"}:
            return score_version == "lazer"
        if self.supports(ServerFeature.SCORE_VERSION):
            return requested_lazer
        return self.default_score_version == "lazer"


@dataclass(frozen=True, slots=True)
class ResolvedServerUser:
    user_id: int
    username: str
    default_mode: PlayMode = PlayMode(Ruleset.OSU)


ScoreScope = Literal["recent", "best", "firsts"]


@dataclass(frozen=True, slots=True)
class UserScoreQuery:
    user_id: int | str
    mode: PlayMode
    scope: ScoreScope = "best"
    legacy_only: bool = False
    include_failed: bool = True
    offset: int = 0
    limit: int = 200


@dataclass(frozen=True, slots=True)
class MapScoreQuery:
    user_id: int | str
    mode: PlayMode
    beatmap: dict
    legacy_only: bool = False
    best_only: bool = False


@dataclass(frozen=True, slots=True)
class MapScores:
    scores: list[UnifiedScore]
    origin: Literal["official", "history", "remote"]
    complete: bool
    position: int | str | None = None


class GameServer(ABC):
    descriptor: ServerDescriptor

    @property
    def id(self) -> str:
        return self.descriptor.id

    @property
    def label(self) -> str:
        return self.descriptor.label

    def supports_mode(self, mode: PlayMode) -> bool:
        return mode in self.descriptor.modes

    def supports(self, feature: ServerFeature, mode: PlayMode | None = None) -> bool:
        return self.descriptor.supports(feature, mode)

    def parse_mode(self, value: int | str | PlayMode) -> PlayMode:
        mode = PlayMode.parse(value)
        if mode is None or not self.supports_mode(mode):
            raise ValueError(f"{self.label} 不支持模式: {value}")
        return mode

    @abstractmethod
    async def resolve_user(self, identifier: str) -> int:
        raise NotImplementedError

    async def resolve_user_profile(self, identifier: str) -> ResolvedServerUser:
        return ResolvedServerUser(await self.resolve_user(identifier), identifier)

    @abstractmethod
    async def get_user(self, user_id: int | str, mode: PlayMode) -> UnifiedUser:
        raise NotImplementedError

    @abstractmethod
    async def get_scores(self, query: UserScoreQuery) -> list[UnifiedScore]:
        raise NotImplementedError

    @abstractmethod
    async def get_map_scores(self, query: MapScoreQuery) -> MapScores:
        raise NotImplementedError


class ServerRegistry:
    def __init__(self, servers=()):
        self._servers: dict[str, GameServer] = {}
        for server in servers:
            self.register(server)

    def register(self, server: GameServer) -> None:
        names = {server.id, *server.descriptor.aliases}
        normalized = {name.strip().lower() for name in names}
        duplicates = normalized.intersection(self._servers)
        if duplicates:
            raise ValueError(f"服务器别名重复: {', '.join(sorted(duplicates))}")
        for name in normalized:
            self._servers[name] = server

    def get(self, name: str) -> GameServer:
        normalized = name.strip().lower()
        try:
            return self._servers[normalized]
        except KeyError as error:
            raise ValueError(f"未知服务器: {name}") from error

    def all(self) -> tuple[GameServer, ...]:
        return tuple(dict.fromkeys(self._servers.values()))
