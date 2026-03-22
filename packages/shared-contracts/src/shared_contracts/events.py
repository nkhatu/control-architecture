from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, Field, TypeAdapter

from .tasks import ApprovalStatus, BeneficiaryStatus, ProvenanceSeed, Rail, TaskStatus


EVENT_TYPE_TASK_CREATED = "task.lifecycle.created.v1"
EVENT_TYPE_TASK_STATE_CHANGED = "task.lifecycle.state_changed.v1"
OutboxStatus = Literal["pending", "in_progress", "completed", "failed"]


class TaskLifecycleTransition(BaseModel):
    from_status: TaskStatus | None = None
    to_status: TaskStatus
    changed_by: str
    reason: str | None = None


class TaskSnapshotState(BaseModel):
    status: TaskStatus
    approval_status: ApprovalStatus
    beneficiary_status: BeneficiaryStatus


class TaskCreatedEventPayload(BaseModel):
    task_id: str
    payment_id: str
    customer_id: str
    rail: Rail
    amount_usd: float
    provenance: ProvenanceSeed
    transition: TaskLifecycleTransition


class TaskStateChangedEventPayload(BaseModel):
    task_id: str
    payment_id: str
    transition: TaskLifecycleTransition
    task_snapshot: TaskSnapshotState


class BaseTaskLifecycleOutboxEvent(BaseModel):
    event_id: str
    aggregate_type: str
    aggregate_id: str
    status: OutboxStatus
    attempt_count: int
    last_error: str | None = None
    claimed_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskCreatedOutboxEvent(BaseTaskLifecycleOutboxEvent):
    event_type: Literal["task.lifecycle.created.v1"] = EVENT_TYPE_TASK_CREATED
    payload: TaskCreatedEventPayload


class TaskStateChangedOutboxEvent(BaseTaskLifecycleOutboxEvent):
    event_type: Literal["task.lifecycle.state_changed.v1"] = EVENT_TYPE_TASK_STATE_CHANGED
    payload: TaskStateChangedEventPayload


TaskLifecycleOutboxEvent: TypeAlias = Annotated[
    TaskCreatedOutboxEvent | TaskStateChangedOutboxEvent,
    Field(discriminator="event_type"),
]

_TASK_LIFECYCLE_OUTBOX_EVENT_ADAPTER = TypeAdapter(TaskLifecycleOutboxEvent)


def parse_task_lifecycle_outbox_event(payload: Any) -> TaskLifecycleOutboxEvent:
    if isinstance(payload, BaseTaskLifecycleOutboxEvent):
        return payload
    if hasattr(payload, "payload"):
        raw_payload = payload.payload
    elif isinstance(payload, dict):
        raw_payload = payload.get("payload")
    else:
        raw_payload = None

    raw_event = {
        "event_id": getattr(payload, "event_id", None) if not isinstance(payload, dict) else payload.get("event_id"),
        "aggregate_type": getattr(payload, "aggregate_type", None) if not isinstance(payload, dict) else payload.get("aggregate_type"),
        "aggregate_id": getattr(payload, "aggregate_id", None) if not isinstance(payload, dict) else payload.get("aggregate_id"),
        "event_type": getattr(payload, "event_type", None) if not isinstance(payload, dict) else payload.get("event_type"),
        "payload": raw_payload,
        "status": getattr(payload, "status", None) if not isinstance(payload, dict) else payload.get("status"),
        "attempt_count": getattr(payload, "attempt_count", None) if not isinstance(payload, dict) else payload.get("attempt_count"),
        "last_error": getattr(payload, "last_error", None) if not isinstance(payload, dict) else payload.get("last_error"),
        "claimed_at": getattr(payload, "claimed_at", None) if not isinstance(payload, dict) else payload.get("claimed_at"),
        "processed_at": getattr(payload, "processed_at", None) if not isinstance(payload, dict) else payload.get("processed_at"),
        "created_at": getattr(payload, "created_at", None) if not isinstance(payload, dict) else payload.get("created_at"),
        "updated_at": getattr(payload, "updated_at", None) if not isinstance(payload, dict) else payload.get("updated_at"),
    }
    return _TASK_LIFECYCLE_OUTBOX_EVENT_ADAPTER.validate_python(raw_event)
