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
DelegationStatus = Literal["queued", "pending", "completed", "failed", "cancelled"]


class ProvenanceSeed(BaseModel):
    initiated_by: str
    last_updated_by: str | None = None
    policy_context_id: str | None = None
    trace_id: str | None = None


class TaskContextView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    payment_id: str
    customer_id: str
    rail: Rail
    amount_usd: float
    status: TaskStatus
    beneficiary_status: BeneficiaryStatus
    approval_status: ApprovalStatus
    task_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None


class TaskProvenanceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    initiated_by: str | None = None
    last_updated_by: str | None = None
    policy_context_id: str | None = None
    trace_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskStateHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_event_id: str | None = None
    from_status: str | None = None
    to_status: str
    changed_by: str
    reason: str | None = None
    created_at: datetime


class ArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artifact_type: str
    artifact_ref: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    trust_level: ArtifactTrustLevel
    created_by: str
    created_at: datetime


class DelegatedWorkView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegation_id: str
    workflow_id: str
    parent_agent_id: str
    delegated_agent_id: str
    delegated_action: str
    capability_id: str | None = None
    status: DelegationStatus
    request_envelope: dict[str, Any] = Field(default_factory=dict)
    response_envelope: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TaskRecordsView(BaseModel):
    provenance: TaskProvenanceView
    state_history: list[TaskStateHistoryEntry] = Field(default_factory=list)
    artifacts: list[ArtifactView] = Field(default_factory=list)
    delegations: list[DelegatedWorkView] = Field(default_factory=list)


class TaskDetailView(TaskContextView):
    provenance: TaskProvenanceView
    state_history: list[TaskStateHistoryEntry] = Field(default_factory=list)
    artifacts: list[ArtifactView] = Field(default_factory=list)
    delegations: list[DelegatedWorkView] = Field(default_factory=list)


def empty_task_records(task_id: str) -> TaskRecordsView:
    return TaskRecordsView(
        provenance=TaskProvenanceView(
            task_id=task_id,
            initiated_by=None,
            last_updated_by=None,
            policy_context_id=None,
            trace_id=None,
            created_at=None,
            updated_at=None,
        ),
        state_history=[],
        artifacts=[],
        delegations=[],
    )


def merge_task_detail(context_task: TaskContextView, records: TaskRecordsView) -> TaskDetailView:
    return TaskDetailView(
        **context_task.model_dump(mode="python"),
        provenance=records.provenance,
        state_history=records.state_history,
        artifacts=records.artifacts,
        delegations=records.delegations,
    )
