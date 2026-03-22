from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any

from shared_contracts.tasks import (
    ApprovalDecisionArtifactContent,
    ApprovalRequestArtifactContent,
    ApprovalRoutingCallbackEnvelope,
    ApprovalRoutingRequestEnvelope,
    ApprovalRoutingRequestPayload,
    ApprovalRoutingResultEnvelope,
    ApprovalTaskSummary,
    BeneficiaryValidationArtifactContent,
    BeneficiaryValidationCapabilityRequest,
    BeneficiaryValidationRequestEnvelope,
    BeneficiaryValidationRequestPayload,
    BeneficiaryValidationResultEnvelope,
    BeneficiaryValidationResultPayload,
    DelegatedWorkView,
    DelegationContext,
    MessageSource,
    MessageTarget,
    TraceContext,
    TrustContext,
)
from .capability_client import CapabilityGatewayClient


PARENT_AGENT_ID = "agent.payment_orchestrator"
COMPLIANCE_AGENT_ID = "agent.compliance_screening"
APPROVAL_ROUTER_AGENT_ID = "agent.approval_router"
APPROVAL_CAPABILITY_ID = "domestic_payment.request_payment_approval"


@dataclass
class DelegatedExecutionResult:
    status: str
    response_envelope: BeneficiaryValidationResultEnvelope | ApprovalRoutingResultEnvelope
    payload: BeneficiaryValidationResultPayload | ApprovalRequestArtifactContent


class DelegatedAgentRouter:
    def __init__(self, capability_client: CapabilityGatewayClient, *, default_ttl_seconds: int = 900) -> None:
        self._capability_client = capability_client
        self._default_ttl_seconds = default_ttl_seconds

    def build_request_envelope(
        self,
        *,
        workflow_id: str,
        task_id: str,
        delegated_agent_id: str,
        delegated_action: str,
        payload: BeneficiaryValidationRequestPayload | ApprovalRoutingRequestPayload,
        scope: list[str],
        trace_id: str | None,
        human_approval_required: bool,
        policy_context_id: str | None = None,
        classification: str = "bounded_delegation",
    ) -> BeneficiaryValidationRequestEnvelope | ApprovalRoutingRequestEnvelope:
        common_fields = {
            "message_id": self._new_id("msg"),
            "correlation_id": self._new_id("corr"),
            "task_id": task_id,
            "workflow_id": workflow_id,
            "timestamp": self._utcnow(),
            "source": MessageSource(
                principal_type="agent",
                principal_id=PARENT_AGENT_ID,
            ),
            "delegation": DelegationContext(
                delegated_by=PARENT_AGENT_ID,
                delegation_chain=[PARENT_AGENT_ID, delegated_agent_id],
                scope=scope,
                expires_at=self._utcnow() + timedelta(seconds=self._default_ttl_seconds),
            ),
            "target": MessageTarget(
                target_type="agent",
                target_id=delegated_agent_id,
                version="v1",
            ),
            "trust": TrustContext(
                classification=classification,
                human_approval_required=human_approval_required,
                policy_context_id=policy_context_id,
            ),
            "trace": TraceContext(
                trace_id=trace_id or self._new_id("trace"),
                span_id=self._new_id("span"),
            ),
        }

        if delegated_action == "beneficiary_validation":
            return BeneficiaryValidationRequestEnvelope(
                **common_fields,
                payload=payload,
            )

        if delegated_action == "approval_routing":
            return ApprovalRoutingRequestEnvelope(
                **common_fields,
                payload=payload,
            )

        raise ValueError(f"Unsupported delegated action for request envelope: {delegated_action}")

    def execute(
        self,
        request_envelope: BeneficiaryValidationRequestEnvelope | ApprovalRoutingRequestEnvelope,
    ) -> DelegatedExecutionResult:
        delegated_agent_id = request_envelope.target.target_id
        delegated_action = request_envelope.payload.delegated_action

        if delegated_agent_id == COMPLIANCE_AGENT_ID and delegated_action == "beneficiary_validation":
            capability_request = request_envelope.payload.capability_request.model_dump(mode="json")
            capability_response = self._capability_client.validate_beneficiary(capability_request)
            payload = BeneficiaryValidationResultPayload(
                delegated_action="beneficiary_validation",
                capability_id=capability_response["capability_id"],
                side_effect_class=capability_response["side_effect_class"],
                validation_result=BeneficiaryValidationArtifactContent.model_validate(capability_response["result"]),
            )
            return DelegatedExecutionResult(
                status="completed",
                response_envelope=self._build_response_envelope(
                    request_envelope=request_envelope,
                    source_agent_id=COMPLIANCE_AGENT_ID,
                    message_type="delegation.result.beneficiary_validation",
                    payload=payload,
                ),
                payload=payload,
            )

        if delegated_agent_id == APPROVAL_ROUTER_AGENT_ID and delegated_action == "approval_routing":
            approval_request_id = self._new_id("apr")
            approval_profile = request_envelope.payload.approval_profile
            payload = ApprovalRequestArtifactContent(
                delegated_action="approval_routing",
                approval_request_id=approval_request_id,
                approval_status="pending",
                approval_profile=approval_profile,
                required_approvals=2 if approval_profile == "dual_approval" else 1,
                route="human_approval_queue",
            )
            return DelegatedExecutionResult(
                status="pending",
                response_envelope=self._build_response_envelope(
                    request_envelope=request_envelope,
                    source_agent_id=APPROVAL_ROUTER_AGENT_ID,
                    message_type="delegation.result.approval_routing",
                    payload=payload,
                ),
                payload=payload,
            )

        raise ValueError(f"Unsupported delegated agent request: {delegated_agent_id}:{delegated_action}")

    def build_approval_completion_envelope(
        self,
        *,
        request_envelope: ApprovalRoutingRequestEnvelope,
        approval_request_id: str,
        approved_by: str,
        approval_note: str | None,
    ) -> ApprovalRoutingCallbackEnvelope:
        return ApprovalRoutingCallbackEnvelope(
            message_id=self._new_id("msg"),
            correlation_id=request_envelope.correlation_id,
            task_id=request_envelope.task_id,
            workflow_id=request_envelope.workflow_id,
            timestamp=self._utcnow(),
            source=MessageSource(
                principal_type="agent",
                principal_id=APPROVAL_ROUTER_AGENT_ID,
            ),
            delegation=request_envelope.delegation,
            target=MessageTarget(
                target_type="agent",
                target_id=PARENT_AGENT_ID,
                version="v1",
            ),
            trust=request_envelope.trust,
            payload=ApprovalDecisionArtifactContent(
                delegated_action="approval_routing",
                approval_request_id=approval_request_id,
                approval_status="approved",
                approved_by=approved_by,
                approval_note=approval_note,
                approved_at=self._utcnow(),
            ),
            trace=TraceContext(
                trace_id=request_envelope.trace.trace_id,
                span_id=self._new_id("span"),
            ),
        )

    def _build_response_envelope(
        self,
        *,
        request_envelope: BeneficiaryValidationRequestEnvelope | ApprovalRoutingRequestEnvelope,
        source_agent_id: str,
        message_type: str,
        payload: BeneficiaryValidationResultPayload | ApprovalRequestArtifactContent,
    ) -> BeneficiaryValidationResultEnvelope | ApprovalRoutingResultEnvelope:
        common_fields = {
            "message_id": self._new_id("msg"),
            "correlation_id": request_envelope.correlation_id,
            "task_id": request_envelope.task_id,
            "workflow_id": request_envelope.workflow_id,
            "timestamp": self._utcnow(),
            "source": MessageSource(
                principal_type="agent",
                principal_id=source_agent_id,
            ),
            "delegation": request_envelope.delegation,
            "target": MessageTarget(
                target_type="agent",
                target_id=PARENT_AGENT_ID,
                version="v1",
            ),
            "trust": request_envelope.trust,
            "trace": TraceContext(
                trace_id=request_envelope.trace.trace_id,
                span_id=self._new_id("span"),
            ),
        }

        if message_type == "delegation.result.beneficiary_validation":
            return BeneficiaryValidationResultEnvelope(
                **common_fields,
                payload=payload,
            )

        if message_type == "delegation.result.approval_routing":
            return ApprovalRoutingResultEnvelope(
                **common_fields,
                payload=payload,
            )

        raise ValueError(f"Unsupported delegated response message type: {message_type}")

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(6)}"

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)
