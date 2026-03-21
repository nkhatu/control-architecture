from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Artifact, Task, TaskStateHistory
from .schemas import ArtifactCreateRequest, TaskCreateRequest, TaskStatePatchRequest


class NoStateChangeError(ValueError):
    """Raised when a state patch would not change any persisted task fields."""


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_task(self, payload: TaskCreateRequest) -> Task:
        provenance = payload.provenance.model_dump()
        provenance["last_updated_by"] = provenance.get("last_updated_by") or provenance["initiated_by"]

        task = Task(
            task_id=payload.task_id or f"task_{uuid4().hex[:12]}",
            payment_id=payload.payment_id or f"pay_{uuid4().hex[:12]}",
            customer_id=payload.customer_id,
            rail=payload.rail,
            amount_usd=payload.amount_usd,
            status=payload.status,
            beneficiary_status=payload.beneficiary_status,
            approval_status=payload.approval_status,
            task_metadata=payload.task_metadata,
            provenance=provenance,
        )
        history = TaskStateHistory(
            task=task,
            from_status=None,
            to_status=payload.status,
            changed_by=provenance["initiated_by"],
            reason="task created",
        )

        self.session.add(task)
        self.session.add(history)
        self.session.commit()

        return self.get_task(task.task_id)

    def get_task(self, task_id: str) -> Task | None:
        statement = (
            select(Task)
            .options(
                selectinload(Task.state_history),
                selectinload(Task.artifacts),
            )
            .where(Task.task_id == task_id)
        )
        return self.session.scalars(statement).unique().one_or_none()

    def update_task_state(self, task_id: str, payload: TaskStatePatchRequest) -> Task | None:
        task = self.get_task(task_id)
        if task is None:
            return None

        approval_status = payload.approval_status or task.approval_status
        beneficiary_status = payload.beneficiary_status or task.beneficiary_status

        if (
            task.status == payload.status
            and task.approval_status == approval_status
            and task.beneficiary_status == beneficiary_status
        ):
            raise NoStateChangeError(f"Task {task_id} already reflects the requested state.")

        previous_status = task.status
        task.status = payload.status

        if payload.approval_status is not None:
            task.approval_status = payload.approval_status

        if payload.beneficiary_status is not None:
            task.beneficiary_status = payload.beneficiary_status

        provenance = dict(task.provenance or {})
        provenance["last_updated_by"] = payload.changed_by
        task.provenance = provenance

        history = TaskStateHistory(
            task_id=task.task_id,
            from_status=previous_status,
            to_status=payload.status,
            changed_by=payload.changed_by,
            reason=payload.reason,
        )

        self.session.add(history)
        self.session.add(task)
        self.session.commit()

        return self.get_task(task.task_id)

    def add_artifact(self, task_id: str, payload: ArtifactCreateRequest) -> Artifact | None:
        task = self.get_task(task_id)
        if task is None:
            return None

        artifact = Artifact(
            task_id=task.task_id,
            artifact_type=payload.artifact_type,
            artifact_ref=payload.artifact_ref,
            content=payload.content,
            trust_level=payload.trust_level,
            created_by=payload.created_by,
        )

        provenance = dict(task.provenance or {})
        provenance["last_updated_by"] = payload.created_by
        task.provenance = provenance

        self.session.add(artifact)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(artifact)

        return artifact
