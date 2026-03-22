from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from .config import AppSettings, get_settings
from .memory_client import MemoryServiceClient, MemoryServiceHttpClient
from .policy_client import PolicyServiceClient, PolicyServiceHttpClient
from .registry import load_registry_snapshot
from .schemas import (
    DomesticPaymentIntakeRequest,
    DomesticPaymentIntakeResponse,
    DomesticPaymentResumeRequest,
    DomesticPaymentResumeResponse,
)
from .service import OrchestrationService, OrchestrationServiceError
from .workflow_client import WorkflowWorkerClient, WorkflowWorkerHttpClient


def create_app(
    settings: AppSettings | None = None,
    memory_service_client: MemoryServiceClient | None = None,
    policy_service_client: PolicyServiceClient | None = None,
    workflow_worker_client: WorkflowWorkerClient | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    registry_snapshot = load_registry_snapshot(app_settings)
    owned_memory_client = memory_service_client is None
    owned_policy_client = policy_service_client is None
    owned_workflow_client = workflow_worker_client is None
    active_memory_client = memory_service_client or MemoryServiceHttpClient(
        app_settings.context_memory_service_base_url,
        app_settings.provenance_service_base_url,
    )
    active_policy_client = policy_service_client or PolicyServiceHttpClient(app_settings.policy_service_base_url)
    active_workflow_client = workflow_worker_client or WorkflowWorkerHttpClient(app_settings.workflow_worker_base_url)
    service = OrchestrationService(
        registry_snapshot,
        active_memory_client,
        active_workflow_client,
        active_policy_client,
        app_name=app_settings.app_name,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.registry_snapshot = registry_snapshot
        app.state.memory_service_client = active_memory_client
        app.state.policy_service_client = active_policy_client
        app.state.workflow_worker_client = active_workflow_client
        app.state.service = service
        yield
        if owned_memory_client:
            active_memory_client.close()
        if owned_policy_client:
            active_policy_client.close()
        if owned_workflow_client:
            active_workflow_client.close()

    app = FastAPI(
        title="Orchestrator API",
        description="Domestic payment intake and coordination service for the PoC.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_service() -> OrchestrationService:
        return service

    @app.get("/health")
    def health() -> dict[str, str]:
        environment = registry_snapshot.control_plane.get("environment", {})
        return {
            "status": "ok",
            "service": app_settings.app_name,
            "mode": environment.get("default_mode", "unknown"),
        }

    @app.get("/metadata")
    def metadata(service: OrchestrationService = Depends(get_service)) -> dict[str, object]:
        return service.metadata(
            app_settings.context_memory_service_base_url,
            app_settings.provenance_service_base_url,
            app_settings.policy_service_base_url,
            app_settings.workflow_worker_base_url,
            app_settings.app_name,
            app_settings.app_env,
        )

    @app.post("/tasks/domestic-payments", response_model=DomesticPaymentIntakeResponse, status_code=status.HTTP_201_CREATED)
    def create_domestic_payment_task(
        payload: DomesticPaymentIntakeRequest,
        service: OrchestrationService = Depends(get_service),
    ) -> DomesticPaymentIntakeResponse:
        try:
            return service.create_domestic_payment_task(payload)
        except OrchestrationServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    @app.post("/tasks/{task_id}/resume", response_model=DomesticPaymentResumeResponse)
    def resume_domestic_payment_task(
        task_id: str,
        payload: DomesticPaymentResumeRequest,
        service: OrchestrationService = Depends(get_service),
    ) -> DomesticPaymentResumeResponse:
        try:
            return service.resume_task(task_id, payload)
        except OrchestrationServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    @app.get("/tasks/{task_id}")
    def get_task(
        task_id: str,
        service: OrchestrationService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            return service.get_task(task_id)
        except OrchestrationServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    return app


app = create_app()
