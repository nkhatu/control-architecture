from __future__ import annotations

import hashlib
from typing import Any

from shared_contracts.tasks import (
    ApprovalRoutingRequestPayload,
    BeneficiaryValidationCapabilityRequest,
    BeneficiaryValidationRequestPayload,
    PaymentReleaseResultArtifactContent,
    DelegatedWorkView,
    TaskDetailView,
)

from .capability_client import CapabilityGatewayClient, CapabilityGatewayError
from .delegation import (
    APPROVAL_CAPABILITY_ID,
    APPROVAL_ROUTER_AGENT_ID,
    COMPLIANCE_AGENT_ID,
    PARENT_AGENT_ID,
    DelegatedAgentRouter,
)
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
        delegated_agent_router: DelegatedAgentRouter | None = None,
        app_name: str = "workflow-worker",
    ) -> None:
        self._memory_client = memory_client
        self._capability_client = capability_client
        self._control_plane_config = control_plane_config
        self._delegated_agent_router = delegated_agent_router or DelegatedAgentRouter(capability_client)
        self._app_name = app_name

    def metadata(
        self,
        context_memory_service_base_url: str,
        provenance_service_base_url: str,
        capability_gateway_base_url: str,
        app_env: str,
    ) -> dict[str, object]:
        environment = self._control_plane_config.get("environment", {})
        return {
            "service": self._app_name,
            "environment": app_env,
            "mode": environment.get("default_mode", "unknown"),
            "context_memory_service_base_url": context_memory_service_base_url,
            "provenance_service_base_url": provenance_service_base_url,
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
            validation_request_envelope = self._delegated_agent_router.build_request_envelope(
                workflow_id=workflow_id,
                task_id=task.task_id,
                delegated_agent_id=COMPLIANCE_AGENT_ID,
                delegated_action="beneficiary_validation",
                scope=["payment.validate"],
                trace_id=payload.request.trace_id,
                human_approval_required=False,
                payload=BeneficiaryValidationRequestPayload(
                    capability_request=BeneficiaryValidationCapabilityRequest(
                        task_id=task.task_id,
                        payment_id=task.payment_id,
                        customer_id=task.customer_id,
                        beneficiary_id=payload.request.beneficiary_id,
                        amount_usd=task.amount_usd,
                        rail=task.rail,
                        trace_id=payload.request.trace_id,
                    )
                ),
            )
            validation_delegation = self._memory_client.create_delegation(
                task.task_id,
                {
                    "workflow_id": workflow_id,
                    "parent_agent_id": PARENT_AGENT_ID,
                    "delegated_agent_id": COMPLIANCE_AGENT_ID,
                    "delegated_action": "beneficiary_validation",
                    "capability_id": CAPABILITY_VALIDATE_BENEFICIARY,
                    "status": "queued",
                    "request_envelope": validation_request_envelope.model_dump(mode="json"),
                },
            )
            validation_execution = self._delegated_agent_router.execute(validation_request_envelope)
            self._memory_client.update_delegation(
                validation_delegation.delegation_id,
                {
                    "status": validation_execution.status,
                    "updated_by": COMPLIANCE_AGENT_ID,
                    "response_envelope": validation_execution.response_envelope.model_dump(mode="json"),
                },
            )
            validation = validation_execution.payload.validation_result
            validation_artifact = self._memory_client.create_artifact(
                task.task_id,
                {
                    "artifact_type": "beneficiary_validation_result",
                    "content": validation.model_dump(mode="json"),
                    "created_by": COMPLIANCE_AGENT_ID,
                },
            )
        except CapabilityGatewayError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class=exc.error_class or "gateway_error") from exc
        except MemoryServiceError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class="memory_error") from exc

        validation_status = validation.status
        beneficiary_status = self._beneficiary_status(validation_status)

        try:
            if validation_status == "validated":
                self._memory_client.patch_task_state(
                    task.task_id,
                    {
                        "status": "validated",
                        "changed_by": self._app_name,
                        "reason": "Beneficiary validation completed.",
                        "beneficiary_status": beneficiary_status,
                        "approval_status": "pending",
                    },
                )
                approval_request_envelope = self._delegated_agent_router.build_request_envelope(
                    workflow_id=workflow_id,
                    task_id=task.task_id,
                    delegated_agent_id=APPROVAL_ROUTER_AGENT_ID,
                    delegated_action="approval_routing",
                    scope=["payment.submit_for_approval"],
                    trace_id=payload.request.trace_id,
                    human_approval_required=True,
                    payload=ApprovalRoutingRequestPayload(
                        approval_profile=payload.policy_decision.approval_profile,
                        task_summary={
                            "task_id": task.task_id,
                            "payment_id": task.payment_id,
                            "customer_id": task.customer_id,
                            "amount_usd": task.amount_usd,
                            "rail": task.rail,
                        },
                    ),
                )
                approval_delegation = self._memory_client.create_delegation(
                    task.task_id,
                    {
                        "workflow_id": workflow_id,
                        "parent_agent_id": PARENT_AGENT_ID,
                        "delegated_agent_id": APPROVAL_ROUTER_AGENT_ID,
                        "delegated_action": "approval_routing",
                        "capability_id": APPROVAL_CAPABILITY_ID,
                        "status": "queued",
                        "request_envelope": approval_request_envelope.model_dump(mode="json"),
                    },
                )
                approval_execution = self._delegated_agent_router.execute(approval_request_envelope)
                self._memory_client.update_delegation(
                    approval_delegation.delegation_id,
                    {
                        "status": approval_execution.status,
                        "updated_by": APPROVAL_ROUTER_AGENT_ID,
                        "response_envelope": approval_execution.response_envelope.model_dump(mode="json"),
                    },
                )
                approval_artifact = self._memory_client.create_artifact(
                    task.task_id,
                    {
                        "artifact_type": "approval_request",
                        "content": approval_execution.payload.model_dump(mode="json"),
                        "created_by": APPROVAL_ROUTER_AGENT_ID,
                    },
                )
                final_task = self._memory_client.patch_task_state(
                    task.task_id,
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
                artifacts_created = [
                    validation_artifact.artifact_type,
                    approval_artifact.artifact_type,
                ]
            else:
                blocked_status = "exception" if validation_status == "needs_review" else "failed"
                final_task = self._memory_client.patch_task_state(
                    task.task_id,
                    {
                        "status": blocked_status,
                        "changed_by": self._app_name,
                        "reason": validation.reason or "Beneficiary validation failed.",
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
                artifacts_created = [validation_artifact.artifact_type]
        except MemoryServiceError as exc:
            raise WorkflowWorkerError(str(exc), status_code=exc.status_code, error_class="memory_error") from exc

        return WorkflowExecutionResponse(
            task=final_task,
            workflow=workflow,
            artifacts_created=artifacts_created,
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

        if task.status != "awaiting_approval":
            raise WorkflowWorkerError(
                f"Task {task_id} is not waiting for approval and cannot be resumed.",
                status_code=409,
                error_class="state_conflict",
            )

        workflow_id = task.task_metadata.get("workflow_id", self._workflow_id(task_id))
        approval_reason = payload.approval_note or "Approval granted. Resume release workflow."
        approval_delegation = self._find_latest_delegation(task, delegated_action="approval_routing", status="pending")
        if approval_delegation is None:
            raise WorkflowWorkerError(
                f"Task {task_id} does not have a pending approval delegation to complete.",
                status_code=409,
                error_class="state_conflict",
            )

        approval_response_envelope = approval_delegation.response_envelope
        approval_request_id = (
            approval_response_envelope.payload.approval_request_id
            if approval_response_envelope is not None
            else None
        )
        if not isinstance(approval_request_id, str) or not approval_request_id:
            raise WorkflowWorkerError(
                f"Task {task_id} has an invalid approval delegation record.",
                status_code=409,
                error_class="state_conflict",
            )

        try:
            approval_completion_envelope = self._delegated_agent_router.build_approval_completion_envelope(
                request_envelope=approval_delegation.request_envelope,
                approval_request_id=approval_request_id,
                approved_by=payload.approved_by,
                approval_note=payload.approval_note,
            )
            self._memory_client.update_delegation(
                approval_delegation.delegation_id,
                {
                    "status": "completed",
                    "updated_by": APPROVAL_ROUTER_AGENT_ID,
                    "response_envelope": approval_completion_envelope.model_dump(mode="json"),
                },
            )
            approval_artifact = self._memory_client.create_artifact(
                task_id,
                {
                    "artifact_type": "approval_decision",
                    "content": approval_completion_envelope.payload.model_dump(mode="json"),
                    "created_by": APPROVAL_ROUTER_AGENT_ID,
                },
            )
            self._memory_client.patch_task_state(
                task_id,
                {
                    "status": "approved",
                    "changed_by": payload.approved_by,
                    "reason": approval_reason,
                    "beneficiary_status": task.beneficiary_status,
                    "approval_status": "approved",
                },
            )
            release_result = self._capability_client.release_payment(
                {
                    "payment_id": task.payment_id,
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
                    "content": PaymentReleaseResultArtifactContent(
                        payment_id=release_result["result"]["payment_id"],
                        status=release_result["result"]["status"],
                        rail=release_result["result"].get("rail"),
                        updated_at=release_result["result"]["updated_at"],
                        error_class=release_result["result"].get("error_class"),
                        explanation=release_result["result"].get("explanation"),
                        mock_rail_outcome=release_result["mock_rail_outcome"],
                        idempotency_key=release_result["idempotency_key"],
                    ).model_dump(mode="json"),
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
                        "beneficiary_status": task.beneficiary_status,
                        "approval_status": "approved",
                    },
                )
                final_task = self._memory_client.patch_task_state(
                    task_id,
                    {
                        "status": "settlement_pending",
                        "changed_by": self._app_name,
                        "reason": release_result["result"].get("explanation") or "Waiting for settlement confirmation.",
                        "beneficiary_status": task.beneficiary_status,
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
                        "beneficiary_status": task.beneficiary_status,
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
                        "beneficiary_status": task.beneficiary_status,
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
            artifacts_created=[approval_artifact.artifact_type, artifact.artifact_type],
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

    def _find_latest_delegation(
        self,
        task: TaskDetailView,
        *,
        delegated_action: str,
        status: str,
    ) -> DelegatedWorkView | None:
        candidates = [
            delegation
            for delegation in task.delegations
            if delegation.delegated_action == delegated_action and delegation.status == status
        ]
        if not candidates:
            return None
        return candidates[-1]
