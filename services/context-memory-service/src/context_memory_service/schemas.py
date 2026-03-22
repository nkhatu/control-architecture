from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Rail = Literal["ach", "same_day_ach", "internal_transfer", "rtp"]
TaskStatus = Literal[
    "received",
    "validated",
    "awaiting_approval",
    "approved",
    "released",
    "settlement_pending",
    "settled",
    "failed",
    "cancelled",
    "pending_reconcile",
    "exception",
]
BeneficiaryStatus = Literal["unknown", "approved", "rejected", "needs_review"]
ApprovalStatus = Literal["not_required", "pending", "approved", "denied", "expired"]
OutboxStatus = Literal["pending", "in_progress", "completed", "failed"]


class ProvenanceSeed(BaseModel):
    initiated_by: str
    last_updated_by: str | None = None
    policy_context_id: str | None = None
    trace_id: str | None = None


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


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    payment_id: str
    customer_id: str
    rail: str
    amount_usd: float
    status: str
    beneficiary_status: str
    approval_status: str
    task_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None = None


class OutboxClaimRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    lease_seconds: int = Field(default=30, ge=1, le=3600)


class OutboxEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    status: str
    attempt_count: int
    last_error: str | None = None
    claimed_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OutboxClaimResponse(BaseModel):
    events: list[OutboxEventResponse] = Field(default_factory=list)


class OutboxFailRequest(BaseModel):
    error_message: str
