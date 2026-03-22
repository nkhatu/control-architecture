from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .config import AppSettings, get_settings, load_yaml_file
from .schemas import IntakeDecisionRequest, PolicyDecisionResponse, ReleaseDecisionRequest
from .service import PolicyService


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    control_plane_config = load_yaml_file(app_settings.resolved_control_plane_config_path)
    service = PolicyService(control_plane_config, app_name=app_settings.app_name)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.control_plane_config = control_plane_config
        app.state.service = service
        yield

    app = FastAPI(
        title="Policy Service",
        description="Deterministic policy decision service for the domestic money movement PoC.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_service() -> PolicyService:
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
    def metadata(service: PolicyService = Depends(get_service)) -> dict[str, object]:
        return service.metadata(app_settings.app_env)

    @app.post("/decisions/intake", response_model=PolicyDecisionResponse)
    def evaluate_intake(
        payload: IntakeDecisionRequest,
        service: PolicyService = Depends(get_service),
    ) -> PolicyDecisionResponse:
        return service.evaluate_intake(payload)

    @app.post("/decisions/release", response_model=PolicyDecisionResponse)
    def evaluate_release(
        payload: ReleaseDecisionRequest,
        service: PolicyService = Depends(get_service),
    ) -> PolicyDecisionResponse:
        return service.evaluate_release(payload)

    return app


app = create_app()
