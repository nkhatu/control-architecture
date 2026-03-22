from __future__ import annotations

from pydantic import BaseModel
from shared_contracts.tasks import (
    ArtifactCreateRequest,
    ArtifactView,
    DelegatedWorkCreateRequest,
    DelegatedWorkUpdateRequest,
    DelegatedWorkView,
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
