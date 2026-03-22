from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .config import AppSettings, get_settings, load_yaml_file
from .context_client import ContextOutboxClient, ContextOutboxHttpClient
from .provenance_client import ProvenanceProjectionClient, ProvenanceProjectionHttpClient
from .schemas import DispatchRequest, DispatchResponse
from .service import EventConsumerService


def create_app(
    settings: AppSettings | None = None,
    context_outbox_client: ContextOutboxClient | None = None,
    provenance_client: ProvenanceProjectionClient | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    control_plane_config = load_yaml_file(app_settings.resolved_control_plane_config_path)
    owned_context_client = context_outbox_client is None
    owned_provenance_client = provenance_client is None
    active_context_client = context_outbox_client or ContextOutboxHttpClient(app_settings.context_memory_service_base_url)
    active_provenance_client = provenance_client or ProvenanceProjectionHttpClient(app_settings.provenance_service_base_url)
    service = EventConsumerService(
        context_outbox_client=active_context_client,
        provenance_client=active_provenance_client,
        app_name=app_settings.app_name,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.service = service
        app.state.control_plane_config = control_plane_config
        yield
        if owned_context_client:
            active_context_client.close()
        if owned_provenance_client:
            active_provenance_client.close()

    app = FastAPI(
        title="Event Consumer",
        description="Projects context outbox events into provenance records.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_service() -> EventConsumerService:
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
    def metadata(service: EventConsumerService = Depends(get_service)) -> dict[str, object]:
        return service.metadata(
            app_settings.context_memory_service_base_url,
            app_settings.provenance_service_base_url,
            app_settings.app_env,
        )

    @app.post("/dispatch/run-once", response_model=DispatchResponse)
    def dispatch_run_once(
        payload: DispatchRequest,
        service: EventConsumerService = Depends(get_service),
    ) -> DispatchResponse:
        return service.process_once(limit=payload.limit, lease_seconds=payload.lease_seconds)

    return app


app = create_app()
