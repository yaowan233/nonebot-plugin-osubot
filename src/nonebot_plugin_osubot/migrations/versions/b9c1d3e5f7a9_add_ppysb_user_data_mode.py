"""add ppysb user data mode

迁移 ID: b9c1d3e5f7a9
父迁移: a8b0c2d4e6f8
创建时间: 2026-08-31 12:00:00.000000

为 ppysb 绑定表新增独立默认模式列（/mode:4 &sb 修改），
与官网和 g0v0 绑定的默认模式互不影响。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b9c1d3e5f7a9"
down_revision: str | Sequence[str] | None = "a8b0c2d4e6f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    with op.batch_alter_table("nonebot_plugin_osubot_sbuserdata", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "osu_mode",
                sa.Integer(),
                server_default="0",
                nullable=False,
                info={"bind_key": "nonebot_plugin_osubot"},
            )
        )


def downgrade(name: str = "") -> None:
    if name:
        return
    with op.batch_alter_table("nonebot_plugin_osubot_sbuserdata", schema=None) as batch_op:
        batch_op.drop_column("osu_mode")
