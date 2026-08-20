"""add selective score history

迁移 ID: 3f1d2b8a6c90
父迁移: 68a04ea31d05
创建时间: 2026-08-19

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "3f1d2b8a6c90"
down_revision: str | Sequence[str] | None = "68a04ea31d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    op.create_table(
        "nonebot_plugin_osubot_scorehistorydata",
        sa.Column("score_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("beatmap_id", sa.BigInteger(), nullable=False),
        sa.Column("ruleset_id", sa.SmallInteger(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("score_id", name=op.f("pk_nonebot_plugin_osubot_scorehistorydata")),
        info={"bind_key": "nonebot_plugin_osubot"},
    )
    with op.batch_alter_table("nonebot_plugin_osubot_scorehistorydata", schema=None) as batch_op:
        batch_op.create_index(
            "ix_nonebot_plugin_osubot_scorehistory_lookup",
            ["user_id", "beatmap_id", "ruleset_id", "ended_at"],
            unique=False,
        )


def downgrade(name: str = "") -> None:
    if name:
        return
    with op.batch_alter_table("nonebot_plugin_osubot_scorehistorydata", schema=None) as batch_op:
        batch_op.drop_index("ix_nonebot_plugin_osubot_scorehistory_lookup")
    op.drop_table("nonebot_plugin_osubot_scorehistorydata")
