from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from .config import AppSettings, get_settings
from .memory_client import MemoryServiceClient, MemoryServiceHttpClient
from .registry import load_registry_snapshot
from .schemas import DomesticPaymentIntakeRequest, DomesticPaymentIntakeResponse
from .service import OrchestrationService, OrchestrationServiceError


def create_app(
    settings: AppSettings | None = None,
    memory_service_client: MemoryServiceClient | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    registry_snapshot = load_registry_snapshot(app_settings)
    owned_memory_client = memory_service_client is None
    active_memory_client = memory_service_client or MemoryServiceHttpClient(app_settings.memory_service_base_url)
    service = OrchestrationService(registry_snapshot, active_memory_client)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.registry_snapshot = registry_snapshot
        app.state.memory_service_client = active_memory_client
        app.state.service = service
        yield
        if owned_memory_client:
            active_memory_client.close()

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
        return service.metadata(app_settings.memory_service_base_url, app_settings.app_name, app_settings.app_env)

    @app.post("/tasks/domestic-payments", response_model=DomesticPaymentIntakeResponse, status_code=status.HTTP_201_CREATED)
    def create_domestic_payment_task(
        payload: DomesticPaymentIntakeRequest,
        service: OrchestrationService = Depends(get_service),
    ) -> DomesticPaymentIntakeResponse:
        try:
            return service.create_domestic_payment_task(payload)
        except OrchestrationServiceError as exc:
            if "outside the configured PoC rail scope" in str(exc):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
            if "missing from the registry" in str(exc):
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    @app.get("/tasks/{task_id}")
    def get_task(
        task_id: str,
        service: OrchestrationService = Depends(get_service),
    ) -> dict[str, object]:
        try:
            return service.get_task(task_id)
        except OrchestrationServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    return app


app = create_app()
