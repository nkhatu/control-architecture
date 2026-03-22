from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias

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
BeneficiaryValidationStatus = Literal["validated", "rejected", "needs_review"]
PolicyDecisionType = Literal["allow", "deny", "escalate", "simulate"]
MockRailOutcome = Literal["success", "reject", "ambiguous"]


class ProvenanceSeed(BaseModel):
    initiated_by: str
    last_updated_by: str | None = None
    policy_context_id: str | None = None
    trace_id: str | None = None


class MessageSource(BaseModel):
    principal_type: str
    principal_id: str
    tenant_id: str | None = None
    session_id: str | None = None


class DelegationContext(BaseModel):
    delegated_by: str
    delegation_chain: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    expires_at: datetime


class MessageTarget(BaseModel):
    target_type: str
    target_id: str
    version: str


class TrustContext(BaseModel):
    classification: str
    human_approval_required: bool
    policy_context_id: str | None = None


class TraceContext(BaseModel):
    trace_id: str
    span_id: str


class ApprovalTaskSummary(BaseModel):
    task_id: str
    payment_id: str
    customer_id: str
    amount_usd: float
    rail: Rail


class BeneficiaryValidationCapabilityRequest(BaseModel):
    task_id: str
    payment_id: str
    customer_id: str
    beneficiary_id: str
    amount_usd: float
    rail: Rail
    trace_id: str | None = None


class BeneficiaryValidationArtifactContent(BaseModel):
    beneficiary_id: str
    status: BeneficiaryValidationStatus
    reason: str | None = None
    validated_at: datetime


class ApprovalRequestArtifactContent(BaseModel):
    delegated_action: Literal["approval_routing"] = "approval_routing"
    approval_request_id: str
    approval_status: ApprovalStatus
    approval_profile: str
    required_approvals: int = Field(ge=1)
    route: str


class ApprovalDecisionArtifactContent(BaseModel):
    delegated_action: Literal["approval_routing"] = "approval_routing"
    approval_request_id: str
    approval_status: ApprovalStatus
    approved_by: str
    approval_note: str | None = None
    approved_at: datetime


class ReleasePolicyDecisionArtifactContent(BaseModel):
    decision: PolicyDecisionType
    reason: str
    approval_profile: str
    execution_mode: str
    recommended_next_capability: str
    requires_manual_escalation: bool = False


class PaymentReleaseResultArtifactContent(BaseModel):
    payment_id: str
    status: TaskStatus
    rail: Rail | None = None
    updated_at: datetime
    error_class: str | None = None
    explanation: str | None = None
    mock_rail_outcome: MockRailOutcome
    idempotency_key: str


ArtifactContent: TypeAlias = (
    BeneficiaryValidationArtifactContent
    | ApprovalRequestArtifactContent
    | ApprovalDecisionArtifactContent
    | ReleasePolicyDecisionArtifactContent
    | PaymentReleaseResultArtifactContent
)


class CommonMessageEnvelopeBase(BaseModel):
    message_id: str
    correlation_id: str
    task_id: str
    workflow_id: str
    timestamp: datetime
    source: MessageSource
    delegation: DelegationContext
    target: MessageTarget
    trust: TrustContext
    trace: TraceContext


class BeneficiaryValidationRequestPayload(BaseModel):
    delegated_action: Literal["beneficiary_validation"] = "beneficiary_validation"
    capability_request: BeneficiaryValidationCapabilityRequest


class ApprovalRoutingRequestPayload(BaseModel):
    delegated_action: Literal["approval_routing"] = "approval_routing"
    approval_profile: str
    task_summary: ApprovalTaskSummary


class BeneficiaryValidationResultPayload(BaseModel):
    delegated_action: Literal["beneficiary_validation"] = "beneficiary_validation"
    capability_id: str
    side_effect_class: str
    validation_result: BeneficiaryValidationArtifactContent


class BeneficiaryValidationRequestEnvelope(CommonMessageEnvelopeBase):
    message_type: Literal["delegation.request.beneficiary_validation"] = "delegation.request.beneficiary_validation"
    payload: BeneficiaryValidationRequestPayload


class ApprovalRoutingRequestEnvelope(CommonMessageEnvelopeBase):
    message_type: Literal["delegation.request.approval_routing"] = "delegation.request.approval_routing"
    payload: ApprovalRoutingRequestPayload


class BeneficiaryValidationResultEnvelope(CommonMessageEnvelopeBase):
    message_type: Literal["delegation.result.beneficiary_validation"] = "delegation.result.beneficiary_validation"
    payload: BeneficiaryValidationResultPayload


class ApprovalRoutingResultEnvelope(CommonMessageEnvelopeBase):
    message_type: Literal["delegation.result.approval_routing"] = "delegation.result.approval_routing"
    payload: ApprovalRequestArtifactContent


class ApprovalRoutingCallbackEnvelope(CommonMessageEnvelopeBase):
    message_type: Literal["delegation.callback.approval_routing"] = "delegation.callback.approval_routing"
    payload: ApprovalDecisionArtifactContent


DelegationRequestEnvelope: TypeAlias = Annotated[
    BeneficiaryValidationRequestEnvelope | ApprovalRoutingRequestEnvelope,
    Field(discriminator="message_type"),
]


DelegationResponseEnvelope: TypeAlias = Annotated[
    BeneficiaryValidationResultEnvelope | ApprovalRoutingResultEnvelope | ApprovalRoutingCallbackEnvelope,
    Field(discriminator="message_type"),
]


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
    content: ArtifactContent
    trust_level: ArtifactTrustLevel
    created_by: str
    created_at: datetime


class ArtifactCreateRequest(BaseModel):
    artifact_type: str
    artifact_ref: str | None = None
    content: ArtifactContent
    trust_level: ArtifactTrustLevel = "trusted"
    created_by: str


class DelegatedWorkView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegation_id: str
    workflow_id: str
    parent_agent_id: str
    delegated_agent_id: str
    delegated_action: str
    capability_id: str | None = None
    status: DelegationStatus
    request_envelope: DelegationRequestEnvelope
    response_envelope: DelegationResponseEnvelope | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DelegatedWorkCreateRequest(BaseModel):
    workflow_id: str
    parent_agent_id: str
    delegated_agent_id: str
    delegated_action: str
    capability_id: str | None = None
    status: DelegationStatus = "queued"
    request_envelope: DelegationRequestEnvelope
    response_envelope: DelegationResponseEnvelope | None = None


class DelegatedWorkUpdateRequest(BaseModel):
    status: DelegationStatus
    updated_by: str
    response_envelope: DelegationResponseEnvelope | None = None


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
