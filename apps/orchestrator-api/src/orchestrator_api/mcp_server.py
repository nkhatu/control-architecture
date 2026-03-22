from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from mcp.server.fastmcp import FastMCP

from .config import AppSettings, get_settings
from .memory_client import MemoryServiceClient, MemoryServiceHttpClient
from .policy_client import PolicyServiceClient, PolicyServiceHttpClient
from .registry import load_registry_snapshot
from .schemas import DomesticPaymentIntakeRequest, DomesticPaymentResumeRequest
from .service import OrchestrationService
from .workflow_client import WorkflowWorkerClient, WorkflowWorkerHttpClient


@dataclass
class McpRuntime:
    settings: AppSettings
    service: OrchestrationService
    memory_client: MemoryServiceClient
    policy_client: PolicyServiceClient
    workflow_client: WorkflowWorkerClient


def create_runtime(
    settings: AppSettings | None = None,
    memory_service_client: MemoryServiceClient | None = None,
    policy_service_client: PolicyServiceClient | None = None,
    workflow_worker_client: WorkflowWorkerClient | None = None,
) -> McpRuntime:
    app_settings = settings or get_settings()
    memory_client = memory_service_client or MemoryServiceHttpClient(
        app_settings.context_memory_service_base_url,
        app_settings.provenance_service_base_url,
        app_settings.event_consumer_base_url,
    )
    policy_client = policy_service_client or PolicyServiceHttpClient(app_settings.policy_service_base_url)
    workflow_client = workflow_worker_client or WorkflowWorkerHttpClient(app_settings.workflow_worker_base_url)
    snapshot = load_registry_snapshot(app_settings)
    service = OrchestrationService(
        snapshot,
        memory_client,
        workflow_client,
        policy_client,
        app_name=app_settings.app_name,
    )
    return McpRuntime(
        settings=app_settings,
        service=service,
        memory_client=memory_client,
        policy_client=policy_client,
        workflow_client=workflow_client,
    )


def create_mcp_server(
    settings: AppSettings | None = None,
    memory_service_client: MemoryServiceClient | None = None,
    policy_service_client: PolicyServiceClient | None = None,
    workflow_worker_client: WorkflowWorkerClient | None = None,
) -> FastMCP:
    runtime = create_runtime(settings, memory_service_client, policy_service_client, workflow_worker_client)

    mcp = FastMCP(
        name="Agentic Money Movement Orchestrator",
        instructions=(
            "Use these tools and resources to intake domestic money movement tasks, "
            "inspect task state, and review the deterministic control-plane context. "
            "This server does not bypass policy or approval gates."
        ),
        host=runtime.settings.mcp_host,
        port=runtime.settings.mcp_port,
        streamable_http_path="/mcp",
        json_response=True,
    )

    @mcp.tool(
        name="create_domestic_payment_task",
        description="Create a domestic payment task through the orchestrator control plane.",
        structured_output=True,
    )
    def create_domestic_payment_task(
        customer_id: str,
        source_account_id: str,
        beneficiary_id: str,
        amount_usd: float,
        rail: str,
        requested_execution_date: str,
        initiated_by: str,
        memo: str | None = None,
        trace_id: str | None = None,
        principal_scopes: list[str] | None = None,
    ) -> dict[str, object]:
        request = DomesticPaymentIntakeRequest(
            customer_id=customer_id,
            source_account_id=source_account_id,
            beneficiary_id=beneficiary_id,
            amount_usd=amount_usd,
            rail=rail,
            requested_execution_date=date.fromisoformat(requested_execution_date),
            initiated_by=initiated_by,
            memo=memo,
            trace_id=trace_id,
            principal_scopes=principal_scopes or ["payment.validate", "payment.submit_for_approval"],
        )
        return runtime.service.create_domestic_payment_task(request).model_dump()

    @mcp.tool(
        name="resume_domestic_payment_task",
        description="Resume a waiting domestic payment task after approval and submit release through the worker.",
        structured_output=True,
    )
    def resume_domestic_payment_task(
        task_id: str,
        approved_by: str,
        approval_note: str | None = None,
        idempotency_key: str | None = None,
        release_mode: str = "execute",
        principal_scopes: list[str] | None = None,
    ) -> dict[str, object]:
        request = DomesticPaymentResumeRequest(
            approved_by=approved_by,
            approval_note=approval_note,
            idempotency_key=idempotency_key,
            release_mode=release_mode,
            principal_scopes=principal_scopes or ["release:domestic_payment"],
        )
        return runtime.service.resume_task(task_id, request).model_dump()

    @mcp.tool(
        name="get_domestic_payment_task",
        description="Fetch the current durable state of a domestic payment task.",
        structured_output=True,
    )
    def get_domestic_payment_task(task_id: str) -> dict[str, object]:
        return runtime.service.get_task(task_id)

    @mcp.tool(
        name="list_orchestrator_registry_summary",
        description="Return the orchestrator control-plane, capability, and agent registry snapshot.",
        structured_output=True,
    )
    def list_orchestrator_registry_summary() -> dict[str, object]:
        return runtime.service.registry_summary()

    @mcp.resource(
        "registry://capabilities",
        name="capability-registry",
        title="Capability Registry",
        description="Machine-readable capability registry for the orchestrator.",
        mime_type="application/json",
    )
    def capability_registry() -> str:
        return json.dumps([item.model_dump() for item in runtime.service.snapshot.capabilities], indent=2)

    @mcp.resource(
        "registry://agents",
        name="agent-registry",
        title="Agent Registry",
        description="Machine-readable agent registry for the orchestrator.",
        mime_type="application/json",
    )
    def agent_registry() -> str:
        return json.dumps([item.model_dump() for item in runtime.service.snapshot.agents], indent=2)

    @mcp.resource(
        "control-plane://current",
        name="control-plane-config",
        title="Current Control Plane Configuration",
        description="Current control-plane configuration loaded by the orchestrator.",
        mime_type="application/json",
    )
    def control_plane_config() -> str:
        return json.dumps(runtime.service.snapshot.control_plane, indent=2)

    @mcp.resource(
        "task://{task_id}",
        name="domestic-payment-task",
        title="Domestic Payment Task",
        description="Read the durable state of a domestic payment task by task id.",
        mime_type="application/json",
    )
    def domestic_payment_task(task_id: str) -> str:
        return json.dumps(runtime.service.get_task(task_id), indent=2)

    @mcp.prompt(
        name="review_domestic_payment_task",
        title="Review Domestic Payment Task",
        description="Generate a review prompt for a domestic payment task using current state and policy metadata.",
    )
    def review_domestic_payment_task(task_id: str) -> str:
        task = runtime.service.get_task(task_id)
        return (
            "Review the following domestic payment task.\n"
            "Summarize the current state, the policy decision, open risks, and the next safe action.\n\n"
            f"{json.dumps(task, indent=2)}"
        )

    return mcp


def main() -> None:
    settings = get_settings()
    server = create_mcp_server(settings)
    server.run(transport=settings.mcp_transport)


if __name__ == "__main__":
    main()
