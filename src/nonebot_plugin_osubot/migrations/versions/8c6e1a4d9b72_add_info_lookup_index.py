"""add info snapshot lookup index

迁移 ID: 8c6e1a4d9b72
父迁移: 3f1d2b8a6c90
创建时间: 2026-08-20

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "8c6e1a4d9b72"
down_revision: str | Sequence[str] | None = "3f1d2b8a6c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    with op.batch_alter_table("nonebot_plugin_osubot_infodata", schema=None) as batch_op:
        batch_op.create_index(
            "ix_nonebot_plugin_osubot_infodata_lookup",
            ["osu_id", "osu_mode", "date"],
            unique=False,
        )


def downgrade(name: str = "") -> None:
    if name:
        return
    with op.batch_alter_table("nonebot_plugin_osubot_infodata", schema=None) as batch_op:
        batch_op.drop_index("ix_nonebot_plugin_osubot_infodata_lookup")
