from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Task
from .schemas import TaskCreateRequest, TaskStatePatchRequest


class NoStateChangeError(ValueError):
    """Raised when a state patch would not change any persisted task fields."""


class TaskContextRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_task(self, payload: TaskCreateRequest) -> Task:
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
        )

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        statement = select(Task).where(Task.task_id == task_id)
        return self.session.scalars(statement).one_or_none()

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

        task.status = payload.status
        if payload.approval_status is not None:
            task.approval_status = payload.approval_status
        if payload.beneficiary_status is not None:
            task.beneficiary_status = payload.beneficiary_status

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task
