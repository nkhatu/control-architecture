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
```

4. Run tests:

```bash
uv run pytest
```

## What Still Needs To Be Set Up

- Backend runtime bootstrap for `orchestrator-api`, `capability-gateway`, `context-memory-service`, `provenance-service`, `workflow-worker`, and `event-consumer`.
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
3. `policy-service` integration
4. `capability-gateway`
5. `workflow-worker`
6. `orchestrator-api`
7. `ops-console`
