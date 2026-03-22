from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from shared_contracts.tasks import (
    ArtifactTrustLevel,
    ArtifactView,
    DelegatedWorkView,
    DelegationStatus,
    ProvenanceSeed,
    TaskProvenanceView,
    TaskRecordsView,
    TaskStateHistoryEntry,
)

class ProvenanceRecordCreateRequest(ProvenanceSeed):
    pass


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


class ProvenanceRecordResponse(TaskProvenanceView):
    pass


class TaskStateHistoryResponse(TaskStateHistoryEntry):
    pass


class ArtifactResponse(ArtifactView):
    pass


class DelegatedWorkResponse(DelegatedWorkView):
    pass


class TaskRecordsResponse(TaskRecordsView):
    pass
