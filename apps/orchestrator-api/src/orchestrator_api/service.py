from __future__ import annotations

from .memory_client import MemoryServiceClient, MemoryServiceError
from .policy import evaluate_intake_policy
from .registry import RegistrySnapshot
from .schemas import (
    DomesticPaymentIntakeRequest,
    DomesticPaymentIntakeResponse,
    DomesticPaymentResumeRequest,
    DomesticPaymentResumeResponse,
    WorkflowProgressResponse,
)
from .workflow_client import WorkflowWorkerClient, WorkflowWorkerError


class OrchestrationServiceError(RuntimeError):
    """Raised when the orchestrator cannot safely complete a request."""


class OrchestrationService:
    def __init__(
        self,
        snapshot: RegistrySnapshot,
        memory_client: MemoryServiceClient,
        workflow_client: WorkflowWorkerClient,
    ):
        self.snapshot = snapshot
        self.memory_client = memory_client
        self.workflow_client = workflow_client

    def metadata(
        self,
        memory_service_base_url: str,
        workflow_worker_base_url: str,
        app_name: str,
        app_env: str,
    ) -> dict[str, object]:
        return {
            "service": app_name,
            "environment": app_env,
            "memory_service_base_url": memory_service_base_url,
            "workflow_worker_base_url": workflow_worker_base_url,
            "capability_count": len(self.snapshot.capabilities),
            "agent_count": len(self.snapshot.agents),
        }

    def list_available_capabilities(self) -> list[str]:
        return [
            capability.id
            for capability in self.snapshot.capabilities
            if capability.category in {"draft", "validation", "approval", "inquiry", "execution"}
        ]

    def list_selected_agents(self) -> list[str]:
        return [
            agent_id
            for agent_id in (
                "agent.payment_orchestrator",
                "agent.compliance_screening",
                "agent.approval_router",
            )
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

        try:
            workflow_result = self.workflow_client.start_workflow(
                {
                    "request": payload.model_dump(mode="json"),
                    "policy_decision": decision.model_dump(),
                    "selected_agents": selected_agents,
                    "available_capabilities": available_capabilities,
                }
            )
        except WorkflowWorkerError as exc:
            raise OrchestrationServiceError(str(exc)) from exc

        return DomesticPaymentIntakeResponse(
            task=workflow_result["task"],
            policy_decision=decision,
            available_capabilities=available_capabilities,
            selected_agents=selected_agents,
            workflow=WorkflowProgressResponse.model_validate(workflow_result["workflow"]),
        )

    def resume_task(
        self,
        task_id: str,
        payload: DomesticPaymentResumeRequest,
    ) -> DomesticPaymentResumeResponse:
        try:
            workflow_result = self.workflow_client.resume_workflow(task_id, payload.model_dump(mode="json"))
        except WorkflowWorkerError as exc:
            raise OrchestrationServiceError(str(exc)) from exc

        return DomesticPaymentResumeResponse(
            task=workflow_result["task"],
            workflow=WorkflowProgressResponse.model_validate(workflow_result["workflow"]),
            release_result=workflow_result.get("release_result"),
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
