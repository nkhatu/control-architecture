# Context Memory Service

This service owns the current operational task snapshot for the PoC.

It is also the write-side source for task lifecycle outbox events. Task creation and task state changes are written with an outbox record in the same transaction so provenance projection does not depend on dual writes.

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
- `POST /outbox/claim`
- `POST /outbox/{event_id}/complete`
- `POST /outbox/{event_id}/fail`

## Outbox Events

The current service emits:

- `task.lifecycle.created.v1`
- `task.lifecycle.state_changed.v1`

`event-consumer` claims these events and projects them into `provenance-service`.

## Local Run

```bash
uv sync --extra dev
uv run uvicorn context_memory_service.main:app --reload --host 0.0.0.0 --port 8002
```
