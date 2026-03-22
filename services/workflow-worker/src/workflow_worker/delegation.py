from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any

from .capability_client import CapabilityGatewayClient


PARENT_AGENT_ID = "agent.payment_orchestrator"
COMPLIANCE_AGENT_ID = "agent.compliance_screening"
APPROVAL_ROUTER_AGENT_ID = "agent.approval_router"
APPROVAL_CAPABILITY_ID = "domestic_payment.request_payment_approval"


@dataclass
class DelegatedExecutionResult:
    status: str
    response_envelope: dict[str, Any]
    payload: dict[str, Any]


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
        payload: dict[str, Any],
        scope: list[str],
        trace_id: str | None,
        human_approval_required: bool,
        policy_context_id: str | None = None,
        classification: str = "bounded_delegation",
    ) -> dict[str, Any]:
        return {
            "message_id": self._new_id("msg"),
            "correlation_id": self._new_id("corr"),
            "task_id": task_id,
            "workflow_id": workflow_id,
            "message_type": f"delegation.request.{delegated_action}",
            "timestamp": self._utcnow().isoformat(),
            "source": {
                "principal_type": "agent",
                "principal_id": PARENT_AGENT_ID,
            },
            "delegation": {
                "delegated_by": PARENT_AGENT_ID,
                "delegation_chain": [PARENT_AGENT_ID, delegated_agent_id],
                "scope": scope,
                "expires_at": (self._utcnow() + timedelta(seconds=self._default_ttl_seconds)).isoformat(),
            },
            "target": {
                "target_type": "agent",
                "target_id": delegated_agent_id,
                "version": "v1",
            },
            "trust": {
                "classification": classification,
                "human_approval_required": human_approval_required,
                "policy_context_id": policy_context_id,
            },
            "payload": payload,
            "trace": {
                "trace_id": trace_id or self._new_id("trace"),
                "span_id": self._new_id("span"),
            },
        }

    def execute(self, request_envelope: dict[str, Any]) -> DelegatedExecutionResult:
        delegated_agent_id = request_envelope["target"]["target_id"]
        delegated_action = request_envelope["payload"]["delegated_action"]

        if delegated_agent_id == COMPLIANCE_AGENT_ID and delegated_action == "beneficiary_validation":
            capability_request = request_envelope["payload"]["capability_request"]
            capability_response = self._capability_client.validate_beneficiary(capability_request)
            payload = {
                "delegated_action": delegated_action,
                "capability_id": capability_response["capability_id"],
                "side_effect_class": capability_response["side_effect_class"],
                "validation_result": capability_response["result"],
            }
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
            approval_profile = request_envelope["payload"]["approval_profile"]
            payload = {
                "delegated_action": delegated_action,
                "approval_request_id": approval_request_id,
                "approval_status": "pending",
                "approval_profile": approval_profile,
                "required_approvals": 2 if approval_profile == "dual_approval" else 1,
                "route": "human_approval_queue",
            }
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
        request_envelope: dict[str, Any],
        approval_request_id: str,
        approved_by: str,
        approval_note: str | None,
    ) -> dict[str, Any]:
        payload = {
            "delegated_action": "approval_routing",
            "approval_request_id": approval_request_id,
            "approval_status": "approved",
            "approved_by": approved_by,
            "approval_note": approval_note,
            "approved_at": self._utcnow().isoformat(),
        }
        return self._build_response_envelope(
            request_envelope=request_envelope,
            source_agent_id=APPROVAL_ROUTER_AGENT_ID,
            message_type="delegation.callback.approval_routing",
            payload=payload,
        )

    def _build_response_envelope(
        self,
        *,
        request_envelope: dict[str, Any],
        source_agent_id: str,
        message_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "message_id": self._new_id("msg"),
            "correlation_id": request_envelope["correlation_id"],
            "task_id": request_envelope["task_id"],
            "workflow_id": request_envelope["workflow_id"],
            "message_type": message_type,
            "timestamp": self._utcnow().isoformat(),
            "source": {
                "principal_type": "agent",
                "principal_id": source_agent_id,
            },
            "delegation": request_envelope["delegation"],
            "target": {
                "target_type": "agent",
                "target_id": PARENT_AGENT_ID,
                "version": "v1",
            },
            "trust": request_envelope["trust"],
            "payload": payload,
            "trace": {
                "trace_id": request_envelope["trace"]["trace_id"],
                "span_id": self._new_id("span"),
            },
        }

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(6)}"

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)
