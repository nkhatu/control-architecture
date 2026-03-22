from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from .config import AppSettings, get_settings, load_control_plane_config
from .database import create_session_factory, create_sqlalchemy_engine, init_db
from .repository import NoStateChangeError, TaskContextRepository
from .schemas import TaskCreateRequest, TaskResponse, TaskStatePatchRequest


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
        title="Context Memory Service",
        description="Current task snapshot boundary for the agentic money movement PoC.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_repository(session: Session = Depends(get_session)) -> TaskContextRepository:
        return TaskContextRepository(session)

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

    @app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
    def create_task(
        payload: TaskCreateRequest,
        repository: TaskContextRepository = Depends(get_repository),
    ) -> TaskResponse:
        return TaskResponse.model_validate(repository.create_task(payload))

    @app.get("/tasks/{task_id}", response_model=TaskResponse)
    def get_task(
        task_id: str,
        repository: TaskContextRepository = Depends(get_repository),
    ) -> TaskResponse:
        task = repository.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} was not found.")
        return TaskResponse.model_validate(task)

    @app.patch("/tasks/{task_id}/state", response_model=TaskResponse)
    def patch_task_state(
        task_id: str,
        payload: TaskStatePatchRequest,
        repository: TaskContextRepository = Depends(get_repository),
    ) -> TaskResponse:
        try:
            task = repository.update_task_state(task_id, payload)
        except NoStateChangeError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} was not found.")

        return TaskResponse.model_validate(task)

    return app


app = create_app()
