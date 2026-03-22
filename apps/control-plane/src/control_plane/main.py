from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .config import AppSettings, get_settings, load_yaml_file
from .schemas import (
    AgentRegistryResponse,
    CapabilityRegistryResponse,
    ControlPlaneDocumentResponse,
    ControlPlaneSnapshotResponse,
    ControlSummaryResponse,
    MetadataResponse,
    VersionSnapshotResponse,
)
from .service import ControlPlaneService


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    control_plane_document = load_yaml_file(app_settings.resolved_control_plane_config_path)
    capability_registry_document = load_yaml_file(app_settings.resolved_capability_registry_path)
    agent_registry_document = load_yaml_file(app_settings.resolved_agent_registry_path)
    service = ControlPlaneService(
        control_plane_document=control_plane_document,
        capability_registry_document=capability_registry_document,
        agent_registry_document=agent_registry_document,
        control_plane_path=app_settings.resolved_control_plane_config_path,
        capability_registry_path=app_settings.resolved_capability_registry_path,
        agent_registry_path=app_settings.resolved_agent_registry_path,
        app_name=app_settings.app_name,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.service = service
        yield

    app = FastAPI(
        title="Control Plane",
        description="Read-only control-plane and registry publishing boundary for the PoC.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_service() -> ControlPlaneService:
        return service

    @app.get("/health")
    def health() -> dict[str, str]:
        environment = control_plane_document.get("environment", {})
        return {
            "status": "ok",
            "service": app_settings.app_name,
            "mode": environment.get("default_mode", "unknown"),
        }

    @app.get("/metadata", response_model=MetadataResponse)
    def metadata(service: ControlPlaneService = Depends(get_service)) -> MetadataResponse:
        return service.metadata(app_settings.app_env)

    @app.get("/control-plane", response_model=ControlPlaneDocumentResponse)
    def control_plane_document(service: ControlPlaneService = Depends(get_service)) -> ControlPlaneDocumentResponse:
        return ControlPlaneDocumentResponse(document=service.control_plane_document())

    @app.get("/controls/summary", response_model=ControlSummaryResponse)
    def control_summary(service: ControlPlaneService = Depends(get_service)) -> ControlSummaryResponse:
        return service.control_summary()

    @app.get("/registries/capabilities", response_model=CapabilityRegistryResponse)
    def capabilities(service: ControlPlaneService = Depends(get_service)) -> CapabilityRegistryResponse:
        return CapabilityRegistryResponse(capabilities=service.capabilities())

    @app.get("/registries/agents", response_model=AgentRegistryResponse)
    def agents(service: ControlPlaneService = Depends(get_service)) -> AgentRegistryResponse:
        return AgentRegistryResponse(agents=service.agents())

    @app.get("/versions/current", response_model=VersionSnapshotResponse)
    def versions(service: ControlPlaneService = Depends(get_service)) -> VersionSnapshotResponse:
        return service.versions()

    @app.get("/snapshot", response_model=ControlPlaneSnapshotResponse)
    def snapshot(service: ControlPlaneService = Depends(get_service)) -> ControlPlaneSnapshotResponse:
        return service.snapshot()

    return app


app = create_app()
