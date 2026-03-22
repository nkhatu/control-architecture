from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from shared_contracts.events import TaskLifecycleOutboxEvent
from shared_contracts.tasks import (
    ApprovalStatus,
    BeneficiaryStatus,
    ProvenanceSeed,
    Rail,
    TaskContextView,
    TaskStatus,
)

OutboxStatus = Literal["pending", "in_progress", "completed", "failed"]


class TaskCreateRequest(BaseModel):
    task_id: str | None = None
    payment_id: str | None = None
    customer_id: str
    rail: Rail
    amount_usd: float = Field(gt=0)
    status: TaskStatus = "received"
    beneficiary_status: BeneficiaryStatus = "unknown"
    approval_status: ApprovalStatus = "pending"
    task_metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: ProvenanceSeed


class TaskStatePatchRequest(BaseModel):
    status: TaskStatus
    changed_by: str
    reason: str | None = None
    approval_status: ApprovalStatus | None = None
    beneficiary_status: BeneficiaryStatus | None = None


class TaskResponse(TaskContextView):
    pass


class OutboxClaimRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    lease_seconds: int = Field(default=30, ge=1, le=3600)


class OutboxClaimResponse(BaseModel):
    events: list[TaskLifecycleOutboxEvent] = Field(default_factory=list)


class OutboxFailRequest(BaseModel):
    error_message: str
