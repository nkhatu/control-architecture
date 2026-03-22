# Local Setup

## Prerequisites

- Docker Desktop or an equivalent local Docker runtime
- `make`
- Node.js 20+ for the future ops console
- Python 3.12+ for backend services and workflow workers

## Initial Setup

1. Copy `.env.example` to `.env`.
2. Review [config/control-plane/default.yaml](/Users/enkay/Documents/Scripts/Control Architecture/config/control-plane/default.yaml) and confirm PoC thresholds.
3. Start local dependencies with `make infra-up`.
4. Confirm ports:
   - Postgres `5432`
   - Redis `6379`
   - NATS `4222`
   - OPA `8181`
   - Temporal `7233`
   - Temporal UI `8080`

## Built Components

The current PoC already includes these runnable components:

- `control-plane`
  - read-only control-plane and registry publishing boundary
  - publishes the control-plane document, capability registry, agent registry, and snapshot/version metadata
- `policy-engine`
  - deterministic intake and release decision boundary
  - reads control settings from `control-plane`, with local file fallback
- `capability-gateway`
  - typed wrappers around the mock domestic rail
  - supports instruction creation, beneficiary validation, release, status lookup, and idempotency replay
  - reads control settings and registry data from `control-plane`, with local file fallback
- `context-memory-service`
  - current task snapshot boundary
  - owns operational task state and the transactional outbox
- `provenance-service`
  - append-only provenance, artifacts, state transitions, and delegated work records
- `event-consumer`
  - projects outbox events from `context-memory-service` into `provenance-service`
  - provides idempotent event-driven consistency for task creation and state changes
- `workflow-worker`
  - drives the payment workflow from intake through validation, approval wait state, release, and ambiguous-result handling
  - reads control settings from `control-plane`, with local file fallback
- `orchestrator-api`
  - intake and coordination boundary for domestic payment tasks
  - reads registry and control data from `control-plane`, with local file fallback
  - calls `policy-engine` for decisions and `workflow-worker` for execution
  - exposes both REST endpoints and an MCP adapter

Shared PoC building blocks already in place:

- split operational state between `context-memory-service` and `provenance-service`
- typed shared contracts in `packages/shared-contracts`
- language-neutral schemas in `packages/capability-schemas`
- delegated-agent runtime for:
  - `agent.payment_orchestrator`
  - `agent.compliance_screening`
  - `agent.approval_router`
- outbox-driven projection from context into provenance
- manual end-to-end runbook in [end-to-end-test.md](/Users/enkay/Documents/Scripts/Control%20Architecture/docs/runbooks/end-to-end-test.md)

## Python Bootstrap

1. Install `uv` if it is not already available.
2. From the repo root, run:

```bash
uv sync --extra dev
```

3. Start the split state services:

```bash
uv run uvicorn context_memory_service.main:app --reload --host 0.0.0.0 --port 8002
uv run uvicorn provenance_service.main:app --reload --host 0.0.0.0 --port 8006
uv run uvicorn event_consumer.main:app --reload --host 0.0.0.0 --port 8007
```

4. Start the coordinating services as needed:

```bash
uv run uvicorn control_plane.main:app --reload --host 0.0.0.0 --port 8008
uv run uvicorn policy_engine.main:app --reload --host 0.0.0.0 --port 8005
uv run uvicorn capability_gateway.main:app --reload --host 0.0.0.0 --port 8001
uv run uvicorn workflow_worker.main:app --reload --host 0.0.0.0 --port 8004
uv run uvicorn orchestrator_api.main:app --reload --host 0.0.0.0 --port 8000
```

5. Run tests:

```bash
uv run pytest
```

For a manual stack walkthrough, see [end-to-end-test.md](/Users/enkay/Documents/Scripts/Control%20Architecture/docs/runbooks/end-to-end-test.md).

## What Still Needs To Be Set Up

- Database schema for task state, approvals, provenance, and audit projections.
- Temporal namespace and workflow registration.
- OPA data loading so policy can read the control-plane thresholds.
- NATS subjects and event naming conventions for approvals, payments, and reconciliation.
- JWT signing and delegated token validation for task-scoped authority.
- A mock rail adapter that can return success, reject, and ambiguous responses.
- Ops console app bootstrapping and the first approval queue screen.

## Recommended Build Order

1. `context-memory-service`
2. `provenance-service`
3. `event-consumer`
4. `control-plane`
5. `policy-engine`
6. `capability-gateway`
7. `workflow-worker`
8. `orchestrator-api`
9. `ops-console`
