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
ArtifactTrustLevel = Literal["trusted", "quarantined", "untrusted"]


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    provenance: ProvenanceRecord


class TaskStatePatchRequest(BaseModel):
    status: TaskStatus
    changed_by: str
    reason: str | None = None
    approval_status: ApprovalStatus | None = None
    beneficiary_status: BeneficiaryStatus | None = None


class ArtifactCreateRequest(BaseModel):
    artifact_type: str
    artifact_ref: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    trust_level: ArtifactTrustLevel = "trusted"
    created_by: str


class TaskStateHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: str | None = None
    to_status: str
    changed_by: str
    reason: str | None = None
    created_at: datetime


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artifact_type: str
    artifact_ref: str | None = None
    content: dict[str, Any]
    trust_level: str
    created_by: str
    created_at: datetime


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
    provenance: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None = None


class TaskDetailResponse(TaskResponse):
    state_history: list[TaskStateHistoryResponse] = Field(default_factory=list)
    artifacts: list[ArtifactResponse] = Field(default_factory=list)
