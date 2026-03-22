# Agentic Domestic Money Movement PoC

This scaffold turns the architecture described in [Protocol-Mediated Agentic Money Movement Control Platform Architecture.pdf](docs/architecture/Protocol-Mediated%20Agentic%20Money%20Movement%20Control%20Platform%20Architecture.pdf) into a proof-of-concept repository shape.

The PoC is intentionally narrow:

- One domestic payment workflow: draft -> validate -> approval -> release -> settlement pending.
- One execution adapter: a mock domestic rail behind the capability gateway.
- One deterministic policy path: `policy-service` decides whether the action is allowed, denied, or escalated using an OPA-aligned control model.
- One split state boundary: `context-memory-service` owns the current task snapshot while `provenance-service` owns append-only evidence.
- One event-driven consistency path: `context-memory-service` emits transactional outbox events and `event-consumer` projects them into `provenance-service`.

## Why this shape

The document's core architectural rule is separation:

- Control plane and policy must stay outside the model.
- Capability wrappers must stay separate from orchestration.
- Workflow state must be durable and queryable.
- Protocol contracts must be explicit and machine-readable.

This repository mirrors that split from day one so the PoC does not collapse into a single service.

## Reference Diagrams

Full architecture document: [Protocol-Mediated Agentic Money Movement Control Platform Architecture.pdf](docs/architecture/Protocol-Mediated%20Agentic%20Money%20Movement%20Control%20Platform%20Architecture.pdf)

### Protocol-Mediated Architecture

![Protocol-Mediated Architecture](docs/architecture/Protocol%20Mediated%20Architecture.jpg)

### Trust Graph

![Trust Graph - Agentic Domestic Money Movement](docs/architecture/Trust%20Graph%20-%20Agentic%20Domestic%20Money%20Movement.jpg)

## Repository Layout

```text
apps/
  ops-console/          operator UI for approvals, review, and investigations
  control-plane-service/ read-only control-plane and registry publishing boundary
  orchestrator-api/     intake API, registry lookups, policy checks, workflow kickoff, MCP server adapter
  policy-service/       deterministic policy decision service and OPA-aligned policy bundle
  capability-gateway/   typed wrappers around mock payment rails
services/
  context-memory-service/ current task snapshot and workflow-operational state
  provenance-service/   append-only provenance, artifacts, and delegation records
  workflow-worker/      Temporal workflows and activities
  event-consumer/       async event handlers and read model updates
packages/
  README.md             package-boundary guide for shared assets
  shared-contracts/     typed shared event payloads and merged task/read-model contracts
  capability-schemas/   shared JSON schemas and protocol envelope
  policy-models/        role maps, thresholds, approval profiles
  security-middleware/  token validation, idempotency, audit helpers
  observability/        trace, metric, and structured log conventions
config/
  control-plane/        default control settings for local PoC
  registry/             capability and agent registry entries
infra/
  kubernetes/           deployment placeholder
  terraform/            infrastructure placeholder
  helm/                 packaging placeholder
docs/
  architecture/         PoC scope and boundaries
  runbooks/             local setup and operator notes
  threat-models/        starter threat model for the PoC
```

## PoC Flow

1. `orchestrator-api` accepts a domestic payment task.
2. `context-memory-service` persists the current task snapshot and writes an outbox event in the same transaction.
3. `event-consumer` claims the outbox event and projects it into `provenance-service` with idempotent replay protection.
4. `orchestrator-api` and `workflow-worker` read merged task detail from `context-memory-service` and `provenance-service`.
5. `policy-service` evaluates explicit intake and release decisions.
6. If allowed, `workflow-worker` drives validation, approval wait states, release, and ambiguous-response holds.
7. `capability-gateway` talks to a mock rail and returns typed release outcomes.

## Package Boundaries

The `packages/` directory is for reusable assets that multiple services import, but which are not deployable services themselves.

- `shared-contracts` contains Python runtime models used directly by backend code. Use it for typed internal event payloads and merged read models.
- `capability-schemas` contains JSON Schema documents. Use it when the contract needs to be language-neutral, published, or validated outside Python.
- `policy-models` contains versioned policy data such as thresholds, approval matrices, and scope maps.
- `security-middleware` and `observability` are support packages for shared enforcement and telemetry conventions.

Rule of thumb:

- If the thing is a Python model imported by backend services, it belongs in `shared-contracts`.
- If the thing is a schema document, it belongs in `capability-schemas`.
- If the thing changes policy behavior through configuration rather than code, it belongs in `policy-models`.

For more detail, see [packages/README.md](packages/README.md).

## Current Implemented Slice

The PoC currently includes:

- `control-plane-service` as a read-only runtime boundary for control-plane and registry publication.
- `context-memory-service` as the durable task snapshot boundary.
- `provenance-service` as the append-only provenance and delegation boundary.
- a transactional outbox in `context-memory-service` for task create and state-change events.
- `event-consumer` as the projection service that reconciles context into provenance.
- `shared-contracts` as the typed contract package for lifecycle events and merged task views.
- `orchestrator-api` as both a REST intake API and an MCP server adapter.
- `policy-service` as the deterministic decision boundary for intake and release checks.
- `workflow-worker` as the service that advances validation, approval wait states, and release.
- a composite task-boundary client that merges context and provenance into one task view for the orchestrator and worker.
- MCP tools, resources, and a review prompt exposed through the orchestrator for controlled task creation and retrieval.

## Delegated Agent Alignment

The current delegated-agent flow is:

- `agent.payment_orchestrator` acts as the parent agent.
- `agent.compliance_screening` handles beneficiary validation.
- `agent.approval_router` handles approval routing.
- approval resume completes the pending delegation before release continues.

This aligns to the trust graph by making the parent agent, delegated agents, and context memory explicit:

- the parent-agent role is implemented in `orchestrator-api` and carried into `workflow-worker`.
- current workflow-operational state is persisted in `context-memory-service`.
- delegated work and evidence are persisted in `provenance-service` with request and response envelopes, status, and provenance.
- compliance screening and approval routing now execute as bounded delegated steps rather than as anonymous internal calls.

This aligns to the platform architecture by preserving the core separation of concerns:

- orchestration remains in `orchestrator-api` and `workflow-worker`.
- current state remains in `context-memory-service`.
- provenance, artifacts, and delegation records remain in `provenance-service`.
- rail-side execution remains behind `capability-gateway`.
- protocol-level delegation data is carried as explicit machine-readable envelopes instead of implicit service calls.

For service-level run commands and MCP details, see [apps/orchestrator-api/README.md](apps/orchestrator-api/README.md).
