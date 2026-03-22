from __future__ import annotations

import hashlib

from shared_contracts.tasks import ReleasePolicyDecisionArtifactContent, TaskDetailView

from .memory_client import MemoryServiceClient, MemoryServiceError
from .policy_client import PolicyEngineClient, PolicyEngineError
from .registry import RegistrySnapshot
from .schemas import (
    DomesticPaymentIntakeRequest,
    DomesticPaymentIntakeResponse,
    DomesticPaymentResumeRequest,
    DomesticPaymentResumeResponse,
    PolicyDecisionResponse,
    WorkflowProgressResponse,
)
from .workflow_client import WorkflowWorkerClient, WorkflowWorkerError


class OrchestrationServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, error_class: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class


class OrchestrationService:
    def __init__(
        self,
        snapshot: RegistrySnapshot,
        memory_client: MemoryServiceClient,
        workflow_client: WorkflowWorkerClient,
        policy_client: PolicyEngineClient,
        app_name: str = "orchestrator-api",
    ):
        self.snapshot = snapshot
        self.memory_client = memory_client
        self.workflow_client = workflow_client
        self.policy_client = policy_client
        self.app_name = app_name

    def metadata(
        self,
        context_memory_service_base_url: str,
        provenance_service_base_url: str,
        policy_engine_base_url: str,
        workflow_worker_base_url: str,
        app_name: str,
        app_env: str,
    ) -> dict[str, object]:
        return {
            "service": app_name,
            "environment": app_env,
            "context_memory_service_base_url": context_memory_service_base_url,
            "provenance_service_base_url": provenance_service_base_url,
            "policy_engine_base_url": policy_engine_base_url,
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
        decision = self._evaluate_intake_policy(payload)
        if decision.decision == "deny":
            raise OrchestrationServiceError(decision.reason, status_code=403, error_class="policy_denied")

        if self.snapshot.get_capability(decision.recommended_next_capability) is None:
            raise OrchestrationServiceError(
                f"Required capability {decision.recommended_next_capability} is missing from the registry.",
                status_code=500,
                error_class="registry_error",
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
            raise OrchestrationServiceError(str(exc), status_code=exc.status_code, error_class=exc.error_class) from exc

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
            task = self.memory_client.get_task(task_id)
        except MemoryServiceError as exc:
            raise OrchestrationServiceError(str(exc), status_code=502, error_class="memory_error") from exc

        idempotency_key = payload.idempotency_key or self._default_idempotency_key(task_id)
        decision = self._evaluate_release_policy(task, payload, idempotency_key)
        if decision.decision == "deny":
            raise OrchestrationServiceError(decision.reason, status_code=403, error_class="policy_denied")
        if decision.decision == "escalate":
            raise OrchestrationServiceError(
                decision.reason,
                status_code=409,
                error_class="policy_escalation_required",
            )
        if decision.decision == "simulate":
            raise OrchestrationServiceError(
                decision.reason,
                status_code=409,
                error_class="policy_simulation_only",
            )

        try:
            self.memory_client.create_artifact(
                task_id,
                {
                    "artifact_type": "release_policy_decision",
                    "content": ReleasePolicyDecisionArtifactContent(**decision.model_dump(mode="json")).model_dump(mode="json"),
                    "created_by": self.app_name,
                },
            )
            workflow_result = self.workflow_client.resume_workflow(
                task_id,
                {
                    "approved_by": payload.approved_by,
                    "approval_note": payload.approval_note,
                    "idempotency_key": idempotency_key,
                    "release_mode": payload.release_mode,
                },
            )
        except MemoryServiceError as exc:
            raise OrchestrationServiceError(str(exc), status_code=502, error_class="memory_error") from exc
        except WorkflowWorkerError as exc:
            raise OrchestrationServiceError(str(exc), status_code=exc.status_code, error_class=exc.error_class) from exc

        return DomesticPaymentResumeResponse(
            task=workflow_result["task"],
            workflow=WorkflowProgressResponse.model_validate(workflow_result["workflow"]),
            release_result=workflow_result.get("release_result"),
        )

    def get_task(self, task_id: str) -> TaskDetailView:
        try:
            return self.memory_client.get_task(task_id)
        except MemoryServiceError as exc:
            raise OrchestrationServiceError(str(exc), status_code=502, error_class="memory_error") from exc

    def registry_summary(self) -> dict[str, object]:
        return {
            "capabilities": [item.model_dump() for item in self.snapshot.capabilities],
            "agents": [item.model_dump() for item in self.snapshot.agents],
            "control_plane": self.snapshot.control_plane,
        }

    def _evaluate_intake_policy(self, payload: DomesticPaymentIntakeRequest) -> PolicyDecisionResponse:
        try:
            decision = self.policy_client.evaluate_intake(
                {
                    "customer_id": payload.customer_id,
                    "rail": payload.rail,
                    "amount_usd": payload.amount_usd,
                    "trace_id": payload.trace_id,
                    "principal": {
                        "actor_id": payload.initiated_by,
                        "scopes": payload.principal_scopes,
                    },
                }
            )
        except PolicyEngineError as exc:
            raise OrchestrationServiceError(str(exc), status_code=exc.status_code, error_class=exc.error_class) from exc

        return PolicyDecisionResponse.model_validate(decision)

    def _evaluate_release_policy(
        self,
        task: TaskDetailView,
        payload: DomesticPaymentResumeRequest,
        idempotency_key: str,
    ) -> PolicyDecisionResponse:
        try:
            decision = self.policy_client.evaluate_release(
                {
                    "payment": {
                        "task_id": task.task_id,
                        "payment_id": task.payment_id,
                        "amount_usd": task.amount_usd,
                        "rail": task.rail,
                        "status": task.status,
                        "approval_status": task.approval_status,
                        "beneficiary_status": task.beneficiary_status,
                        "task_metadata": task.task_metadata,
                    },
                    "principal": {
                        "actor_id": payload.approved_by,
                        "scopes": payload.principal_scopes,
                    },
                    "request": {
                        "approved_by": payload.approved_by,
                        "approval_note": payload.approval_note,
                        "approval_outcome": "approved",
                        "idempotency_key": idempotency_key,
                        "release_mode": payload.release_mode,
                    },
                    "trace_id": task.provenance.trace_id,
                }
            )
        except PolicyEngineError as exc:
            raise OrchestrationServiceError(str(exc), status_code=exc.status_code, error_class=exc.error_class) from exc

        return PolicyDecisionResponse.model_validate(decision)

    def _default_idempotency_key(self, task_id: str) -> str:
        digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16]
        return f"release-{digest}"
