# Local Setup

## Prerequisites

- Docker Desktop or an equivalent local Docker runtime
- `make`
- Node.js 20+ for the ops console
- Python 3.12+ for backend services and workflow workers

## Initial Setup

1. Copy `.env.example` to `.env`.
2. Review [config/control-plane/default.yaml](../../config/control-plane/default.yaml) and confirm PoC thresholds.
3. Start local dependencies with `make infra-up`.
4. Confirm ports:
   - Postgres `5432`
   - Redis `6379`
   - NATS `4222`
   - OPA `8181`
   - Temporal `7233`
   - Temporal UI `8080`

## Implementation Status

| Area | Status | Current State | What Still Needs To Be Built |
| --- | --- | --- | --- |
| `control-plane` | Built | Read-only control-plane and registry publishing boundary with snapshot/version endpoints | Versioned write APIs, approval/audit workflow for control changes |
| `policy-engine` | Built | Deterministic intake and release decisions, reading from `control-plane` with local fallback | Real OPA-backed evaluation path and bundle/data loading |
| `capability-gateway` | Built | Typed mock rail wrappers for instruction creation, beneficiary validation, release, status, and idempotency replay | Real bank/rail adapter beyond the mock rail |
| `context-memory-service` | Built | Current task snapshot boundary with transactional outbox | Production persistence hardening and full migration flow against Postgres |
| `provenance-service` | Built | Append-only provenance, artifacts, state transitions, and delegated work records | Additional provenance projection types beyond the current slice |
| `event-consumer` | Built | Idempotent projection of task create and state-change outbox events into provenance | Broader event coverage and durable broker-backed runtime |
| `workflow-worker` | Built | End-to-end workflow from intake through validation, approval wait, release, and ambiguous-result handling | Temporal-native execution instead of the current local HTTP worker flow |
| `orchestrator-api` | Built | REST intake/resume APIs plus MCP adapter, reading from `control-plane` and coordinating policy + workflow | Broader protocol surface and tighter runtime policy provenance/version pinning |
| Split state boundary | Built | `context-memory-service` and `provenance-service` are separated | Stronger consistency and replay handling across more record types |
| Shared contracts | Built | Typed Python contracts in `packages/shared-contracts` and JSON schemas in `packages/capability-schemas` | More typed transport DTOs for remaining loose payloads |
| Delegated-agent runtime | Built | Parent/delegated flow for `agent.payment_orchestrator`, `agent.compliance_screening`, and `agent.approval_router` | Broader delegated execution coverage for additional actions |
| End-to-end runbook | Built | Manual walkthrough in [end-to-end-test.md](./end-to-end-test.md) | Optional automation of the runbook as a scripted smoke test |
| Database and infra | Partial | Local Docker scaffolding exists | Full Postgres-backed runtime, migrations in deployed flow, NATS subjects, Temporal namespace/workflow registration |
| Security and auth | Partial | Basic structure only | JWT signing, delegated token validation, scoped authority enforcement, audit hardening |
| Ops console | Built | React/Vite operator console with a top-menu layout for overview, payment intake, approvals, task explorer, and exception review, plus approval-backed release | Server-side queue/list endpoints, deeper investigation views, and authenticated operator sessions |

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

For a manual stack walkthrough, see [end-to-end-test.md](./end-to-end-test.md).

## Frontend Bootstrap

From the repo root:

```bash
cd apps/ops-console
npm install
npm run dev
```

The dev server listens on port `3000` by default and proxies:

- `/api/orchestrator` -> `http://127.0.0.1:8000`
- `/api/control-plane` -> `http://127.0.0.1:8008`

Current UI notes:

- The console uses a top menu instead of a single long page.
- The main operator views are `Overview`, `Create Payment`, `Approvals`, `Task Explorer`, and `Exceptions`.
- The current visual theme is blue and is fully local to `apps/ops-console/src/styles.css`.

## Remaining Setup Focus

- Temporal namespace and workflow registration
- OPA data loading so policy can read the control-plane thresholds
- NATS subjects and event naming conventions for approvals, payments, and reconciliation
- JWT signing and delegated token validation for task-scoped authority

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
