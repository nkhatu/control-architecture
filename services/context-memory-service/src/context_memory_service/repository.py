from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OutboxEvent, Task
from .schemas import TaskCreateRequest, TaskStatePatchRequest


EVENT_TYPE_TASK_CREATED = "task.lifecycle.created.v1"
EVENT_TYPE_TASK_STATE_CHANGED = "task.lifecycle.state_changed.v1"


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
        outbox_event = OutboxEvent(
            event_id=f"evt_{uuid4().hex[:12]}",
            aggregate_type="task",
            aggregate_id=task.task_id,
            event_type=EVENT_TYPE_TASK_CREATED,
            payload={
                "task_id": task.task_id,
                "payment_id": task.payment_id,
                "customer_id": task.customer_id,
                "rail": task.rail,
                "amount_usd": float(task.amount_usd),
                "provenance": payload.provenance.model_dump(),
                "transition": {
                    "from_status": None,
                    "to_status": task.status,
                    "changed_by": payload.provenance.initiated_by,
                    "reason": "task created",
                },
            },
            status="pending",
        )

        self.session.add(task)
        self.session.add(outbox_event)
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

        previous_status = task.status
        task.status = payload.status
        if payload.approval_status is not None:
            task.approval_status = payload.approval_status
        if payload.beneficiary_status is not None:
            task.beneficiary_status = payload.beneficiary_status

        outbox_event = OutboxEvent(
            event_id=f"evt_{uuid4().hex[:12]}",
            aggregate_type="task",
            aggregate_id=task.task_id,
            event_type=EVENT_TYPE_TASK_STATE_CHANGED,
            payload={
                "task_id": task.task_id,
                "payment_id": task.payment_id,
                "transition": {
                    "from_status": previous_status,
                    "to_status": payload.status,
                    "changed_by": payload.changed_by,
                    "reason": payload.reason,
                },
                "task_snapshot": {
                    "status": task.status,
                    "approval_status": task.approval_status,
                    "beneficiary_status": task.beneficiary_status,
                },
            },
            status="pending",
        )

        self.session.add(task)
        self.session.add(outbox_event)
        self.session.commit()
        self.session.refresh(task)
        return task

    def claim_outbox_events(self, *, limit: int, lease_seconds: int) -> list[OutboxEvent]:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=lease_seconds)
        statement = (
            select(OutboxEvent)
            .where(
                (OutboxEvent.status.in_(("pending", "failed")))
                | ((OutboxEvent.status == "in_progress") & (OutboxEvent.claimed_at != None) & (OutboxEvent.claimed_at < stale_before))
            )
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        )
        events = list(self.session.scalars(statement).all())
        for event in events:
            event.status = "in_progress"
            event.attempt_count += 1
            event.claimed_at = now
            self.session.add(event)
        self.session.commit()
        return events

    def complete_outbox_event(self, event_id: str) -> OutboxEvent | None:
        event = self.get_outbox_event(event_id)
        if event is None:
            return None
        event.status = "completed"
        event.last_error = None
        event.processed_at = datetime.now(timezone.utc)
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def fail_outbox_event(self, event_id: str, *, error_message: str) -> OutboxEvent | None:
        event = self.get_outbox_event(event_id)
        if event is None:
            return None
        event.status = "failed"
        event.last_error = error_message
        event.claimed_at = None
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def get_outbox_event(self, event_id: str) -> OutboxEvent | None:
        statement = select(OutboxEvent).where(OutboxEvent.event_id == event_id)
        return self.session.scalars(statement).one_or_none()
