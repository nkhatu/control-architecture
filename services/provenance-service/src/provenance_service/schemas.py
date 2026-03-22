from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ArtifactTrustLevel = Literal["trusted", "quarantined", "untrusted"]
DelegationStatus = Literal["queued", "pending", "completed", "failed", "cancelled"]


class ProvenanceRecordCreateRequest(BaseModel):
    initiated_by: str
    last_updated_by: str | None = None
    policy_context_id: str | None = None
    trace_id: str | None = None


class TaskStateTransitionCreateRequest(BaseModel):
    source_event_id: str | None = None
    from_status: str | None = None
    to_status: str
    changed_by: str
    reason: str | None = None


class ArtifactCreateRequest(BaseModel):
    artifact_type: str
    artifact_ref: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    trust_level: ArtifactTrustLevel = "trusted"
    created_by: str


class DelegatedWorkCreateRequest(BaseModel):
    workflow_id: str
    parent_agent_id: str
    delegated_agent_id: str
    delegated_action: str
    capability_id: str | None = None
    status: DelegationStatus = "queued"
    request_envelope: dict[str, Any] = Field(default_factory=dict)
    response_envelope: dict[str, Any] | None = None


class DelegatedWorkUpdateRequest(BaseModel):
    status: DelegationStatus
    updated_by: str
    response_envelope: dict[str, Any] | None = None


class ProvenanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    initiated_by: str
    last_updated_by: str
    policy_context_id: str | None = None
    trace_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TaskStateHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_event_id: str | None = None
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


class DelegatedWorkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegation_id: str
    workflow_id: str
    parent_agent_id: str
    delegated_agent_id: str
    delegated_action: str
    capability_id: str | None = None
    status: str
    request_envelope: dict[str, Any]
    response_envelope: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TaskRecordsResponse(BaseModel):
    provenance: ProvenanceRecordResponse
    state_history: list[TaskStateHistoryResponse] = Field(default_factory=list)
    artifacts: list[ArtifactResponse] = Field(default_factory=list)
    delegations: list[DelegatedWorkResponse] = Field(default_factory=list)
