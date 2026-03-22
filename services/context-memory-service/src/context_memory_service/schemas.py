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


class TaskStatePatchRequest(BaseModel):
    status: TaskStatus
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
