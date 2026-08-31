from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from .api import get_server
from .database import G0v0UserData, SbUserData, UserData


@dataclass(frozen=True, slots=True)
class BindingSpec:
    model: type[Any]
    bind_command: str
    missing_message: str
    stores_default_mode: bool = False
    default_mode_subject: str = ""
    friendly_mode_labels: bool = False

    def mode_of(self, binding: Any) -> str:
        return str(binding.osu_mode) if self.stores_default_mode else "0"


_BINDINGS = {
    "osu": BindingSpec(
        model=UserData,
        bind_command="/bind",
        missing_message="该账号尚未绑定，请输入 /bind 用户名 绑定账号",
        stores_default_mode=True,
    ),
    "ppysb": BindingSpec(
        model=SbUserData,
        bind_command="/sbbind",
        missing_message="该账号尚未绑定 sb 服务器，请输入 /sbbind 用户名 绑定账号",
        stores_default_mode=True,
        default_mode_subject=" ppysb ",
        friendly_mode_labels=True,
    ),
    "g0v0": BindingSpec(
        model=G0v0UserData,
        bind_command="/gubind",
        missing_message="该账号尚未绑定 g0v0 服务器，请输入 /gubind 用户名 绑定账号",
        stores_default_mode=True,
        default_mode_subject=" g0v0 ",
        friendly_mode_labels=True,
    ),
}


def get_binding_spec(source: str) -> BindingSpec:
    return _BINDINGS[get_server(source).id]


async def find_binding(source: str, platform_user_ids: str | list[str], *, session_factory=None) -> Any | None:
    candidates = [platform_user_ids] if isinstance(platform_user_ids, str) else platform_user_ids
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        return None
    spec = get_binding_spec(source)
    session_factory = session_factory or get_session
    async with session_factory() as session:
        for user_id in candidates:
            binding = await session.scalar(select(spec.model).where(spec.model.user_id == user_id))
            if binding:
                return binding
    return None
