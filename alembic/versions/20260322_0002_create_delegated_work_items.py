"""create delegated work items

Revision ID: 20260322_0002
Revises: 20260322_0001
Create Date: 2026-03-22 00:15:00
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260322_0002"
down_revision: str | None = "20260322_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delegated_work_items",
        sa.Column("delegation_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("parent_agent_id", sa.String(length=128), nullable=False),
        sa.Column("delegated_agent_id", sa.String(length=128), nullable=False),
        sa.Column("delegated_action", sa.String(length=128), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_envelope", sa.JSON(), nullable=False),
        sa.Column("response_envelope", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"]),
        sa.PrimaryKeyConstraint("delegation_id"),
    )
    op.create_index("ix_delegated_work_items_task_id", "delegated_work_items", ["task_id"], unique=False)
    op.create_index("ix_delegated_work_items_workflow_id", "delegated_work_items", ["workflow_id"], unique=False)
    op.create_index("ix_delegated_work_items_delegated_agent_id", "delegated_work_items", ["delegated_agent_id"], unique=False)
    op.create_index("ix_delegated_work_items_delegated_action", "delegated_work_items", ["delegated_action"], unique=False)
    op.create_index("ix_delegated_work_items_status", "delegated_work_items", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_delegated_work_items_status", table_name="delegated_work_items")
    op.drop_index("ix_delegated_work_items_delegated_action", table_name="delegated_work_items")
    op.drop_index("ix_delegated_work_items_delegated_agent_id", table_name="delegated_work_items")
    op.drop_index("ix_delegated_work_items_workflow_id", table_name="delegated_work_items")
    op.drop_index("ix_delegated_work_items_task_id", table_name="delegated_work_items")
    op.drop_table("delegated_work_items")
