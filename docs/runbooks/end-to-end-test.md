# End-to-End Test

This runbook walks through the current manual end-to-end flow for the PoC:

1. Start the local services.
2. Create a domestic payment task through `orchestrator-api`.
3. Resume the task after approval.
4. Verify the final merged task state.

This flow uses local SQLite files for `context-memory-service` and `provenance-service` so you can run the stack without Postgres.

## Prerequisites

- Work from the repo root: [Control Architecture](/Users/enkay/Documents/Scripts/Control%20Architecture)
- Use Python 3.12+ with `uv` installed
- Install dependencies first:

```bash
uv sync --extra dev
```

## Terminal 1: Context Memory

```bash
CONTEXT_MEMORY_AUTO_CREATE_SCHEMA=true \
CONTEXT_MEMORY_DATABASE_URL=sqlite+pysqlite:///./.tmp-context.db \
uv run uvicorn context_memory_service.main:app --reload --host 0.0.0.0 --port 8002
```

## Terminal 2: Provenance

```bash
PROVENANCE_AUTO_CREATE_SCHEMA=true \
PROVENANCE_DATABASE_URL=sqlite+pysqlite:///./.tmp-provenance.db \
uv run uvicorn provenance_service.main:app --reload --host 0.0.0.0 --port 8006
```

## Terminal 3: Event Consumer

```bash
uv run uvicorn event_consumer.main:app --reload --host 0.0.0.0 --port 8007
```

## Terminal 4: Control Plane

```bash
uv run uvicorn control_plane.main:app --reload --host 0.0.0.0 --port 8008
```

## Terminal 5: Policy Engine

```bash
uv run uvicorn policy_engine.main:app --reload --host 0.0.0.0 --port 8005
```

## Terminal 6: Capability Gateway

```bash
uv run uvicorn capability_gateway.main:app --reload --host 0.0.0.0 --port 8001
```

## Terminal 7: Workflow Worker

```bash
uv run uvicorn workflow_worker.main:app --reload --host 0.0.0.0 --port 8004
```

## Terminal 8: Orchestrator API

```bash
uv run uvicorn orchestrator_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Verify Service Health

Run these from a separate terminal after the services are up:

```bash
curl http://127.0.0.1:8008/health
curl http://127.0.0.1:8005/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8004/health
curl http://127.0.0.1:8000/health
```

Expected:

- each endpoint returns `200 OK`
- `control-plane`, `policy-engine`, `workflow-worker`, and `orchestrator-api` report `dry_run` mode

## Create a Domestic Payment Task

Run:

```bash
curl -s http://127.0.0.1:8000/tasks/domestic-payments \
  -H 'content-type: application/json' \
  -d '{
    "customer_id": "cust_123",
    "source_account_id": "acct_001",
    "beneficiary_id": "ben_001",
    "amount_usd": 2500,
    "rail": "ach",
    "requested_execution_date": "2026-03-24",
    "initiated_by": "user.neil",
    "trace_id": "tr_manual_001"
  }'
```

Expected in the response:

- `policy_decision.decision` is `allow`
- `task.status` is `awaiting_approval`
- `workflow.workflow_state` is `waiting_for_approval`
- `task.delegations` includes both:
  - `agent.compliance_screening`
  - `agent.approval_router`

Copy the returned `task.task_id` value for the next step.

## Resume After Approval

Replace `<TASK_ID>` with the value returned from the previous step:

```bash
curl -s http://127.0.0.1:8000/tasks/<TASK_ID>/resume \
  -H 'content-type: application/json' \
  -d '{
    "approved_by": "user.ops_approver",
    "approval_note": "Approved for release.",
    "release_mode": "execute"
  }'
```

Expected in the response:

- `task.status` is `settlement_pending`
- `workflow.workflow_state` is `release_completed`
- `release_result.status` is `settlement_pending`

## Fetch the Final Task View

```bash
curl -s http://127.0.0.1:8000/tasks/<TASK_ID>
```

Expected in the response:

- merged task detail from `context-memory-service` and `provenance-service`
- `status` is `settlement_pending`
- `state_history` is present
- `artifacts` includes:
  - `beneficiary_validation_result`
  - `approval_request`
  - `release_policy_decision`
  - `payment_release_result`
- `delegations` shows the delegated workflow records

## Optional Control-Plane Verification

These checks confirm that the stack is reading from `control-plane`:

```bash
curl -s http://127.0.0.1:8008/snapshot
curl -s http://127.0.0.1:8008/controls/summary
```

Expected:

- the snapshot includes `control_plane`, `capabilities`, and `agents`
- the summary includes `kill_switch_enabled`, approval thresholds, and release controls

## Automated Regression Check

Run the full automated suite when you are done:

```bash
uv run pytest
```

Expected:

```text
33 passed
```

## Cleanup

Stop the running services with `Ctrl+C` in each terminal.

If you want to remove the temporary SQLite files created by this run:

```bash
rm -f .tmp-context.db .tmp-provenance.db
```
