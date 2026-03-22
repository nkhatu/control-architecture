# Event Consumer

This service projects context outbox events into provenance records.

Current responsibilities:

- claim lifecycle outbox events from `context-memory-service`
- create provenance records in `provenance-service`
- append state transitions with idempotent replay protection
- mark outbox events complete or failed
- provide a simple `run-once` dispatch endpoint for local PoC coordination

Current supported event types:

- `task.lifecycle.created.v1`
- `task.lifecycle.state_changed.v1`

## Initial API Surface

- `GET /health`
- `GET /metadata`
- `POST /dispatch/run-once`

## Local Run

```bash
uv sync --extra dev
uv run uvicorn event_consumer.main:app --reload --host 0.0.0.0 --port 8007
```
