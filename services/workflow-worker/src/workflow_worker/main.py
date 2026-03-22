from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from .capability_client import CapabilityGatewayClient, CapabilityGatewayHttpClient
from .config import AppSettings, get_settings, load_yaml_file
from .memory_client import MemoryServiceClient, MemoryServiceHttpClient
from .schemas import WorkflowExecutionResponse, WorkflowResumeRequest, WorkflowStartRequest
from .service import WorkflowWorkerError, WorkflowWorkerService


def create_app(
    settings: AppSettings | None = None,
    memory_service_client: MemoryServiceClient | None = None,
    capability_gateway_client: CapabilityGatewayClient | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    control_plane_config = load_yaml_file(app_settings.resolved_control_plane_config_path)
    owned_memory_client = memory_service_client is None
    owned_capability_client = capability_gateway_client is None
    active_memory_client = memory_service_client or MemoryServiceHttpClient(
        app_settings.context_memory_service_base_url,
        app_settings.provenance_service_base_url,
        app_settings.event_consumer_base_url,
    )
    active_capability_client = capability_gateway_client or CapabilityGatewayHttpClient(
        app_settings.capability_gateway_base_url
    )
    service = WorkflowWorkerService(
        memory_client=active_memory_client,
        capability_client=active_capability_client,
        control_plane_config=control_plane_config,
        app_name=app_settings.app_name,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.service = service
        yield
        if owned_memory_client:
            active_memory_client.close()
        if owned_capability_client:
            active_capability_client.close()

    app = FastAPI(
        title="Workflow Worker",
        description="Executes the domestic payment workflow across context-memory-service, provenance-service, and capability-gateway.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_service() -> WorkflowWorkerService:
        return service

    @app.get("/health")
    def health() -> dict[str, str]:
        environment = control_plane_config.get("environment", {})
        return {
            "status": "ok",
            "service": app_settings.app_name,
            "mode": environment.get("default_mode", "unknown"),
        }

    @app.get("/metadata")
    def metadata(service: WorkflowWorkerService = Depends(get_service)) -> dict[str, object]:
        return service.metadata(
            context_memory_service_base_url=app_settings.context_memory_service_base_url,
            provenance_service_base_url=app_settings.provenance_service_base_url,
            capability_gateway_base_url=app_settings.capability_gateway_base_url,
            app_env=app_settings.app_env,
        )

    @app.post(
        "/workflows/domestic-payments/start",
        response_model=WorkflowExecutionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def start_domestic_payment_workflow(
        payload: WorkflowStartRequest,
        service: WorkflowWorkerService = Depends(get_service),
    ) -> WorkflowExecutionResponse:
        try:
            return service.start_domestic_payment_workflow(payload)
        except WorkflowWorkerError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    @app.post(
        "/workflows/domestic-payments/{task_id}/resume",
        response_model=WorkflowExecutionResponse,
    )
    def resume_domestic_payment_workflow(
        task_id: str,
        payload: WorkflowResumeRequest,
        service: WorkflowWorkerService = Depends(get_service),
    ) -> WorkflowExecutionResponse:
        try:
            return service.resume_domestic_payment_workflow(task_id, payload)
        except WorkflowWorkerError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    return app


app = create_app()
