# Memory Service

This service is the explicit task-state boundary for the PoC.

What it stores:

- task objective
- payment attributes such as rail, amount, and beneficiary
- approval state
- recent validated tool outputs
- provenance references
- unresolved issues and hold reasons

What it should not do:

- infer workflow state from chat history
- mix trusted workflow data with untrusted uploaded content
- decide policy

Recommended first API surface:

- `POST /tasks`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}/state`
- `POST /tasks/{task_id}/artifacts`
- `POST /tasks/{task_id}/delegations`
- `PATCH /delegations/{delegation_id}`

## Bootstrap Status

This service now has a runnable FastAPI skeleton under [main.py](/Users/enkay/Documents/Scripts/Control Architecture/services/memory-service/src/memory_service/main.py) with SQLAlchemy models for:

- `tasks`
- `task_state_history`
- `artifacts`
- `delegated_work_items`

## Local Run

From the repo root:

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn memory_service.main:app --reload --host 0.0.0.0 --port 8002
```

## Local Test

```bash
uv run pytest
```

## Migration Workflow

Create the schema in the local database:

```bash
uv run alembic upgrade head
```

Generate a new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "describe change"
```
