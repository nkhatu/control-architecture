from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from .config import AppSettings, get_settings, load_control_plane_config
from .database import create_session_factory, create_sqlalchemy_engine, init_db
from .repository import ProvenanceRepository
from .schemas import (
    ArtifactCreateRequest,
    ArtifactResponse,
    DelegatedWorkCreateRequest,
    DelegatedWorkResponse,
    DelegatedWorkUpdateRequest,
    ProvenanceRecordCreateRequest,
    ProvenanceRecordResponse,
    TaskRecordsResponse,
    TaskStateHistoryResponse,
    TaskStateTransitionCreateRequest,
)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    engine = create_sqlalchemy_engine(app_settings.resolved_database_url)
    session_factory = create_session_factory(engine)
    control_plane_config = load_control_plane_config(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app_settings.auto_create_schema:
            init_db(engine)
        app.state.settings = app_settings
        app.state.session_factory = session_factory
        app.state.control_plane_config = control_plane_config
        yield
        engine.dispose()

    app = FastAPI(
        title="Provenance Service",
        description="Append-only provenance, evidence, and delegation boundary for the PoC.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_repository(session: Session = Depends(get_session)) -> ProvenanceRepository:
        return ProvenanceRepository(session)

    @app.get("/health")
    def health() -> dict[str, str]:
        environment = control_plane_config.get("environment", {})
        return {
            "status": "ok",
            "service": app_settings.app_name,
            "mode": environment.get("default_mode", "unknown"),
        }

    @app.get("/metadata")
    def metadata() -> dict[str, object]:
        database_backend = app_settings.resolved_database_url.split(":", maxsplit=1)[0]
        return {
            "service": app_settings.app_name,
            "environment": app_settings.app_env,
            "database_backend": database_backend,
            "control_plane_config": control_plane_config,
        }

    @app.post("/tasks/{task_id}/provenance", response_model=ProvenanceRecordResponse, status_code=status.HTTP_201_CREATED)
    def create_task_provenance(
        task_id: str,
        payload: ProvenanceRecordCreateRequest,
        repository: ProvenanceRepository = Depends(get_repository),
    ) -> ProvenanceRecordResponse:
        record = repository.create_task_provenance(task_id, payload)
        return ProvenanceRecordResponse.model_validate(record)

    @app.get("/tasks/{task_id}/records", response_model=TaskRecordsResponse)
    def get_task_records(
        task_id: str,
        repository: ProvenanceRepository = Depends(get_repository),
    ) -> TaskRecordsResponse:
        record = repository.get_task_provenance(task_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} provenance was not found.")
        return TaskRecordsResponse(
            provenance=ProvenanceRecordResponse.model_validate(record),
            state_history=[TaskStateHistoryResponse.model_validate(item) for item in record.state_history],
            artifacts=[ArtifactResponse.model_validate(item) for item in record.artifacts],
            delegations=[DelegatedWorkResponse.model_validate(item) for item in record.delegations],
        )

    @app.post(
        "/tasks/{task_id}/state-transitions",
        response_model=TaskStateHistoryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_state_transition(
        task_id: str,
        payload: TaskStateTransitionCreateRequest,
        repository: ProvenanceRepository = Depends(get_repository),
    ) -> TaskStateHistoryResponse:
        transition = repository.add_state_transition(task_id, payload)
        if transition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} provenance was not found.")
        return TaskStateHistoryResponse.model_validate(transition)

    @app.post("/tasks/{task_id}/artifacts", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
    def create_artifact(
        task_id: str,
        payload: ArtifactCreateRequest,
        repository: ProvenanceRepository = Depends(get_repository),
    ) -> ArtifactResponse:
        artifact = repository.add_artifact(task_id, payload)
        if artifact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} provenance was not found.")
        return ArtifactResponse.model_validate(artifact)

    @app.post("/tasks/{task_id}/delegations", response_model=DelegatedWorkResponse, status_code=status.HTTP_201_CREATED)
    def create_delegation(
        task_id: str,
        payload: DelegatedWorkCreateRequest,
        repository: ProvenanceRepository = Depends(get_repository),
    ) -> DelegatedWorkResponse:
        delegation = repository.create_delegation(task_id, payload)
        if delegation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} provenance was not found.")
        return DelegatedWorkResponse.model_validate(delegation)

    @app.get("/delegations/{delegation_id}", response_model=DelegatedWorkResponse)
    def get_delegation(
        delegation_id: str,
        repository: ProvenanceRepository = Depends(get_repository),
    ) -> DelegatedWorkResponse:
        delegation = repository.get_delegation(delegation_id)
        if delegation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Delegation {delegation_id} was not found.")
        return DelegatedWorkResponse.model_validate(delegation)

    @app.patch("/delegations/{delegation_id}", response_model=DelegatedWorkResponse)
    def patch_delegation(
        delegation_id: str,
        payload: DelegatedWorkUpdateRequest,
        repository: ProvenanceRepository = Depends(get_repository),
    ) -> DelegatedWorkResponse:
        delegation = repository.update_delegation(delegation_id, payload)
        if delegation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Delegation {delegation_id} was not found.")
        return DelegatedWorkResponse.model_validate(delegation)

    return app


app = create_app()
