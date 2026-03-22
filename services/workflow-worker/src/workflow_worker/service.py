from __future__ import annotations

import hashlib
from typing import Any

from .capability_client import CapabilityGatewayClient, CapabilityGatewayError
from .memory_client import MemoryServiceClient, MemoryServiceError
from .schemas import WorkflowExecutionResponse, WorkflowProgress, WorkflowResumeRequest, WorkflowStartRequest


CAPABILITY_CREATE_INSTRUCTION = "domestic_payment.create_instruction"
CAPABILITY_VALIDATE_BENEFICIARY = "domestic_payment.validate_beneficiary_account"
CAPABILITY_RELEASE_PAYMENT = "domestic_payment.release_approved_payment"


class WorkflowWorkerError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, error_class: str = "workflow_error") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class


class WorkflowWorkerService:
    def __init__(
        self,
        *,
        memory_client: MemoryServiceClient,
        capability_client: CapabilityGatewayClient,
        control_plane_config: dict[str, Any],
        app_name: str = "workflow-worker",
    ) -> None:
        self._memory_client = memory_client
        self._capability_client = capability_client
        self._control_plane_config = control_plane_config
        self._app_name = app_name

    def metadata(self, memory_service_base_url: str, capability_gateway_base_url: str, app_env: str) -> dict[str, object]:
        environment = self._control_plane_config.get("environment", {})
        return {
            "service": self._app_name,
            "environment": app_env,
            "mode": environment.get("default_mode", "unknown"),
            "memory_service_base_url": memory_service_base_url,
            "capability_gateway_base_url": capability_gateway_base_url,
        }

    def start_domestic_payment_workflow(self, payload: WorkflowStartRequest) -> WorkflowExecutionResponse:
        try:
            instruction = self._capability_client.create_instruction(
                {
                    "customer_id": payload.request.customer_id,
                    "source_account_id": payload.request.source_account_id,
                    "beneficiary_id": payload.request.beneficiary_id,
                    "amount_usd": payload.request.amount_usd,
                    "rail": payload.request.rail,
                    "requested_execution_date": payload.request.requested_execution_date.isoformat(),
                    "memo": payload.request.memo,
                    "initiated_by": payload.request.initiated_by,
                    "trace_id": payload.request.trace_id,
                }
            )
            workflow_id = self._workflow_id(instruction["task"]["task_id"])
            task = self._memory_client.create_task(
                {
                    "task_id": instruction["task"]["task_id"],
                    "payment_id": instruction["task"]["payment_id"],
                    "customer_id": payload.request.customer_id,
                    "rail": payload.request.rail,
                    "amount_usd": payload.request.amount_usd,
                    "status": "received",
                    "beneficiary_status": "unknown",
                    "approval_status": "pending",
                    "task_metadata": {
                        "source_account_id": payload.request.source_account_id,
                        "beneficiary_id": payload.request.beneficiary_id,
                        "requested_execution_date": payload.request.requested_execution_date.isoformat(),
                        "memo": payload.request.memo,
                        "principal_scopes": payload.request.principal_scopes,
                        "policy_decision": payload.policy_decision.model_dump(),
                        "selected_agents": payload.selected_agents,
                        "available_capabilities": payload.available_capabilities,
                        "gateway_instruction_id": instruction["instruction_id"],
                        "workflow_id": workflow_id,
                    },
                    "provenance": {
                        "initiated_by": payload.request.initiated_by,
                        "last_updated_by": self._app_name,
                        "trace_id": payload.request.trace_id,
                    },
                }
            )
            validation = self._capability_client.validate_beneficiary(
                {
                    "task_id": task["task_id"],
                    "payment_id": task["payment_id"],
                    "customer_id": task["customer_id"],
                    "beneficiary_id": payload.request.beneficiary_id,
                    "amount_usd": task["amount_usd"],
                    "rail": task["rail"],
                    "trace_id": payload.request.trace_id,
                }
            )
            artifact = self._memory_client.create_artifact(
                task["task_id"],
                {
                    "artifact_type": "beneficiary_validation_result",
                    "content": validation["result"],
                    "created_by": self._app_name,
                },
            )
        except CapabilityGatewayError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class=exc.error_class or "gateway_error") from exc
        except MemoryServiceError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class="memory_error") from exc

        validation_status = validation["result"]["status"]
        beneficiary_status = self._beneficiary_status(validation_status)

        try:
            if validation_status == "validated":
                self._memory_client.patch_task_state(
                    task["task_id"],
                    {
                        "status": "validated",
                        "changed_by": self._app_name,
                        "reason": "Beneficiary validation completed.",
                        "beneficiary_status": beneficiary_status,
                        "approval_status": "pending",
                    },
                )
                final_task = self._memory_client.patch_task_state(
                    task["task_id"],
                    {
                        "status": "awaiting_approval",
                        "changed_by": self._app_name,
                        "reason": "Workflow is waiting for human approval before release.",
                        "beneficiary_status": beneficiary_status,
                        "approval_status": "pending",
                    },
                )
                workflow = WorkflowProgress(
                    workflow_id=workflow_id,
                    workflow_state="waiting_for_approval",
                    next_action="resume_after_approval",
                    last_capability=CAPABILITY_VALIDATE_BENEFICIARY,
                )
            else:
                blocked_status = "exception" if validation_status == "needs_review" else "failed"
                final_task = self._memory_client.patch_task_state(
                    task["task_id"],
                    {
                        "status": blocked_status,
                        "changed_by": self._app_name,
                        "reason": validation["result"].get("reason") or "Beneficiary validation failed.",
                        "beneficiary_status": beneficiary_status,
                        "approval_status": "pending",
                    },
                )
                workflow = WorkflowProgress(
                    workflow_id=workflow_id,
                    workflow_state="blocked",
                    next_action="manual_review",
                    last_capability=CAPABILITY_VALIDATE_BENEFICIARY,
                )
        except MemoryServiceError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class="memory_error") from exc

        return WorkflowExecutionResponse(
            task=final_task,
            workflow=workflow,
            artifacts_created=[artifact["artifact_type"]],
        )

    def resume_domestic_payment_workflow(
        self,
        task_id: str,
        payload: WorkflowResumeRequest,
    ) -> WorkflowExecutionResponse:
        try:
            task = self._memory_client.get_task(task_id)
        except MemoryServiceError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class="memory_error") from exc

        if task["status"] != "awaiting_approval":
            raise WorkflowWorkerError(
                f"Task {task_id} is not waiting for approval and cannot be resumed.",
                status_code=409,
                error_class="state_conflict",
            )

        workflow_id = task["task_metadata"].get("workflow_id", self._workflow_id(task_id))
        approval_reason = payload.approval_note or "Approval granted. Resume release workflow."

        try:
            self._memory_client.patch_task_state(
                task_id,
                {
                    "status": "approved",
                    "changed_by": payload.approved_by,
                    "reason": approval_reason,
                    "beneficiary_status": task["beneficiary_status"],
                    "approval_status": "approved",
                },
            )
            release_result = self._capability_client.release_payment(
                {
                    "payment_id": task["payment_id"],
                    "task_id": task_id,
                    "idempotency_key": payload.idempotency_key or self._default_idempotency_key(task_id),
                    "released_by": payload.approved_by,
                    "release_mode": payload.release_mode,
                }
            )
            artifact = self._memory_client.create_artifact(
                task_id,
                {
                    "artifact_type": "payment_release_result",
                    "content": {
                        **release_result["result"],
                        "mock_rail_outcome": release_result["mock_rail_outcome"],
                        "idempotency_key": release_result["idempotency_key"],
                    },
                    "created_by": self._app_name,
                },
            )
        except CapabilityGatewayError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class=exc.error_class or "gateway_error") from exc
        except MemoryServiceError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class="memory_error") from exc

        try:
            if release_result["result"]["status"] == "settlement_pending":
                self._memory_client.patch_task_state(
                    task_id,
                    {
                        "status": "released",
                        "changed_by": self._app_name,
                        "reason": "Release request accepted by capability gateway.",
                        "beneficiary_status": task["beneficiary_status"],
                        "approval_status": "approved",
                    },
                )
                final_task = self._memory_client.patch_task_state(
                    task_id,
                    {
                        "status": "settlement_pending",
                        "changed_by": self._app_name,
                        "reason": release_result["result"].get("explanation") or "Waiting for settlement confirmation.",
                        "beneficiary_status": task["beneficiary_status"],
                        "approval_status": "approved",
                    },
                )
                workflow = WorkflowProgress(
                    workflow_id=workflow_id,
                    workflow_state="release_submitted",
                    next_action="wait_for_settlement",
                    last_capability=CAPABILITY_RELEASE_PAYMENT,
                )
            elif release_result["result"]["status"] == "pending_reconcile":
                final_task = self._memory_client.patch_task_state(
                    task_id,
                    {
                        "status": "pending_reconcile",
                        "changed_by": self._app_name,
                        "reason": release_result["result"].get("explanation") or "Release outcome was ambiguous.",
                        "beneficiary_status": task["beneficiary_status"],
                        "approval_status": "approved",
                    },
                )
                workflow = WorkflowProgress(
                    workflow_id=workflow_id,
                    workflow_state="pending_reconcile",
                    next_action="manual_reconciliation",
                    last_capability=CAPABILITY_RELEASE_PAYMENT,
                )
            else:
                final_task = self._memory_client.patch_task_state(
                    task_id,
                    {
                        "status": "failed",
                        "changed_by": self._app_name,
                        "reason": release_result["result"].get("explanation") or "Release request failed.",
                        "beneficiary_status": task["beneficiary_status"],
                        "approval_status": "approved",
                    },
                )
                workflow = WorkflowProgress(
                    workflow_id=workflow_id,
                    workflow_state="failed",
                    next_action="manual_recovery",
                    last_capability=CAPABILITY_RELEASE_PAYMENT,
                )
        except MemoryServiceError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class="memory_error") from exc

        return WorkflowExecutionResponse(
            task=final_task,
            workflow=workflow,
            artifacts_created=[artifact["artifact_type"]],
            release_result=release_result,
        )

    def _workflow_id(self, task_id: str) -> str:
        return f"wf_{task_id}"

    def _beneficiary_status(self, validation_status: str) -> str:
        mapping = {
            "validated": "approved",
            "rejected": "rejected",
            "needs_review": "needs_review",
        }
        return mapping[validation_status]

    def _default_idempotency_key(self, task_id: str) -> str:
        digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16]
        return f"release-{digest}"
