# Context Memory Service

This service owns the current operational task snapshot for the PoC.

It stores:

- task identity and payment identity
- rail and amount
- current workflow status
- current beneficiary status
- current approval status
- operational task metadata needed to continue the workflow

It does not own:

- append-only provenance
- artifacts and evidence records
- delegated request and response envelopes
- state-transition history

## Initial API Surface

- `POST /tasks`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}/state`

## Local Run

```bash
uv sync --extra dev
uv run uvicorn context_memory_service.main:app --reload --host 0.0.0.0 --port 8002
```
