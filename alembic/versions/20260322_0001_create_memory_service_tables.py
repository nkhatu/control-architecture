"""create memory service tables

Revision ID: 20260322_0001
Revises:
Create Date: 2026-03-22 00:00:01
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260322_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("payment_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("rail", sa.String(length=32), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("beneficiary_status", sa.String(length=32), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("task_metadata", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_tasks_customer_id", "tasks", ["customer_id"], unique=False)
    op.create_index("ix_tasks_payment_id", "tasks", ["payment_id"], unique=True)
    op.create_index("ix_tasks_status", "tasks", ["status"], unique=False)

    op.create_table(
        "task_state_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_state_history_task_id", "task_state_history", ["task_id"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_ref", sa.String(length=255), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("trust_level", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_task_id", "artifacts", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_artifacts_task_id", table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index("ix_task_state_history_task_id", table_name="task_state_history")
    op.drop_table("task_state_history")

    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_payment_id", table_name="tasks")
    op.drop_index("ix_tasks_customer_id", table_name="tasks")
    op.drop_table("tasks")
