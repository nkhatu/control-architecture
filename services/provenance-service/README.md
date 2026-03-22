# Provenance Service

This service owns append-only provenance and evidence records for the PoC.

It is the projection target for context lifecycle events. State-transition writes support idempotent replay through `source_event_id`, so the same outbox event can be retried safely.

It stores:

- task provenance identity and trace references
- state-transition history
- policy and workflow artifacts
- delegated request and response envelopes

It does not own:

- the current operational task snapshot
- the current status used as the workflow source of truth

## Initial API Surface

- `POST /tasks/{task_id}/provenance`
- `GET /tasks/{task_id}/records`
- `POST /tasks/{task_id}/state-transitions`
- `POST /tasks/{task_id}/artifacts`
- `POST /tasks/{task_id}/delegations`
- `PATCH /delegations/{delegation_id}`

## Projection Notes

- `event-consumer` creates the task provenance record on `task.lifecycle.created.v1`.
- `event-consumer` appends state transitions on `task.lifecycle.state_changed.v1`.
- direct writes remain in place for artifacts and delegations in the current PoC slice.

## Local Run

```bash
uv sync --extra dev
uv run uvicorn provenance_service.main:app --reload --host 0.0.0.0 --port 8006
```
