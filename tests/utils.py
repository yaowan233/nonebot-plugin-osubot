"""Shared helpers for mocking SQLAlchemy async sessions."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock


def make_mock_session() -> AsyncMock:
    """Return a mock AsyncSession with commonly used methods pre-configured."""
    session = AsyncMock()
    session.add = MagicMock()          # not a coroutine
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock()
    return session


def patch_session(module_path: str, session: AsyncMock):
    """Return a unittest.mock.patch context manager that replaces get_session
    in *module_path* with an async context manager yielding *session*.

    Usage::

        session = make_mock_session()
        session.scalar.return_value = some_value
        with patch_session("nonebot_plugin_osubot.matcher.bind", session):
            async with app.test_matcher(bind) as ctx:
                ...
    """
    from unittest.mock import patch

    @asynccontextmanager
    async def _fake_get_session():
        yield session

    return patch(f"{module_path}.get_session", _fake_get_session)


def make_mock_user(
    user_id: str = "12345678",
    osu_id: int = 114514,
    osu_name: str = "test_player",
    osu_mode: int = 0,
    lazer_mode: bool = False,
) -> MagicMock:
    """Return a MagicMock that looks like a UserData row."""
    user = MagicMock()
    user.user_id = user_id
    user.osu_id = osu_id
    user.osu_name = osu_name
    user.osu_mode = osu_mode
    user.lazer_mode = lazer_mode
    return user
