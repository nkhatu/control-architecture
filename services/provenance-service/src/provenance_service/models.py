from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TaskProvenance(Base):
    __tablename__ = "task_provenance"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    initiated_by: Mapped[str] = mapped_column(String(128))
    last_updated_by: Mapped[str] = mapped_column(String(128))
    policy_context_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    state_history: Mapped[list["TaskStateTransition"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStateTransition.created_at",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="Artifact.created_at",
    )
    delegations: Mapped[list["DelegatedWorkItem"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="DelegatedWorkItem.created_at",
    )


class TaskStateTransition(Base):
    __tablename__ = "task_state_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task_provenance.task_id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    changed_by: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[TaskProvenance] = relationship(back_populates="state_history")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task_provenance.task_id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64))
    artifact_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trust_level: Mapped[str] = mapped_column(String(32), default="trusted")
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[TaskProvenance] = relationship(back_populates="artifacts")


class DelegatedWorkItem(Base):
    __tablename__ = "delegated_work_items"

    delegation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task_provenance.task_id"), index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_agent_id: Mapped[str] = mapped_column(String(128))
    delegated_agent_id: Mapped[str] = mapped_column(String(128), index=True)
    delegated_action: Mapped[str] = mapped_column(String(128), index=True)
    capability_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    request_envelope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_envelope: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    task: Mapped[TaskProvenance] = relationship(back_populates="delegations")
