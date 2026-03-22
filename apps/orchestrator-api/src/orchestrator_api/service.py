from __future__ import annotations

from .memory_client import MemoryServiceClient, MemoryServiceError
from .policy import evaluate_intake_policy
from .registry import RegistrySnapshot
from .schemas import DomesticPaymentIntakeRequest, DomesticPaymentIntakeResponse


class OrchestrationServiceError(RuntimeError):
    """Raised when the orchestrator cannot safely complete a request."""


class OrchestrationService:
    def __init__(self, snapshot: RegistrySnapshot, memory_client: MemoryServiceClient):
        self.snapshot = snapshot
        self.memory_client = memory_client

    def metadata(self, memory_service_base_url: str, app_name: str, app_env: str) -> dict[str, object]:
        return {
            "service": app_name,
            "environment": app_env,
            "memory_service_base_url": memory_service_base_url,
            "capability_count": len(self.snapshot.capabilities),
            "agent_count": len(self.snapshot.agents),
        }

    def list_available_capabilities(self) -> list[str]:
        return [
            capability.id
            for capability in self.snapshot.capabilities
            if capability.category in {"draft", "validation", "approval", "inquiry"}
        ]

    def list_selected_agents(self) -> list[str]:
        return [
            agent_id
            for agent_id in ("agent.payment_orchestrator", "agent.compliance_screening")
            if self.snapshot.get_agent(agent_id) is not None
        ]

    def create_domestic_payment_task(
        self,
        payload: DomesticPaymentIntakeRequest,
    ) -> DomesticPaymentIntakeResponse:
        decision = evaluate_intake_policy(payload, self.snapshot.control_plane)
        if decision.decision == "deny":
            raise OrchestrationServiceError(decision.reason)

        if self.snapshot.get_capability(decision.recommended_next_capability) is None:
            raise OrchestrationServiceError(
                f"Required capability {decision.recommended_next_capability} is missing from the registry."
            )

        selected_agents = self.list_selected_agents()
        available_capabilities = self.list_available_capabilities()

        memory_payload = {
            "customer_id": payload.customer_id,
            "rail": payload.rail,
            "amount_usd": payload.amount_usd,
            "status": "received",
            "beneficiary_status": "unknown",
            "approval_status": "pending",
            "task_metadata": {
                "source_account_id": payload.source_account_id,
                "beneficiary_id": payload.beneficiary_id,
                "requested_execution_date": payload.requested_execution_date.isoformat(),
                "memo": payload.memo,
                "principal_scopes": payload.principal_scopes,
                "policy_decision": decision.model_dump(),
                "selected_agents": selected_agents,
            },
            "provenance": {
                "initiated_by": payload.initiated_by,
                "last_updated_by": "agent.payment_orchestrator",
                "trace_id": payload.trace_id,
            },
        }

        try:
            task = self.memory_client.create_task(memory_payload)
        except MemoryServiceError as exc:
            raise OrchestrationServiceError(str(exc)) from exc

        return DomesticPaymentIntakeResponse(
            task=task,
            policy_decision=decision,
            available_capabilities=available_capabilities,
            selected_agents=selected_agents,
        )

    def get_task(self, task_id: str) -> dict[str, object]:
        try:
            return self.memory_client.get_task(task_id)
        except MemoryServiceError as exc:
            raise OrchestrationServiceError(str(exc)) from exc

    def registry_summary(self) -> dict[str, object]:
        return {
            "capabilities": [item.model_dump() for item in self.snapshot.capabilities],
            "agents": [item.model_dump() for item in self.snapshot.agents],
            "control_plane": self.snapshot.control_plane,
        }
