# Workflow Worker

This service owns durable workflow execution.

Use Temporal for:

- payment intake workflow
- validation workflow steps
- approval wait states
- release orchestration
- ambiguous response handling
- reconciliation handoff

The first workflow should model these states:

- `received`
- `validated`
- `awaiting_approval`
- `approved`
- `released`
- `settlement_pending`
- `pending_reconcile`
- `failed`
- `cancelled`

## Bootstrap Status

This service now has a runnable FastAPI skeleton under [main.py](/Users/enkay/Documents/Scripts/Control%20Architecture/services/workflow-worker/src/workflow_worker/main.py).

Current PoC slice:

- starts the domestic payment workflow after orchestrator intake
- creates the payment instruction through `capability-gateway`
- persists workflow-owned state transitions in `memory-service`
- performs beneficiary validation and waits in `awaiting_approval`
- resumes after approval and drives release to `settlement_pending`, `pending_reconcile`, or `failed`

## Local Run

From the repo root:

```bash
uv sync --extra dev
uv run uvicorn workflow_worker.main:app --reload --host 0.0.0.0 --port 8004
```

## Local Test

```bash
uv run pytest
```
