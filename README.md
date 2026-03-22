# Agentic Domestic Money Movement PoC

This scaffold turns the architecture described in [Protocol-Mediated Agentic Money Movement Control Platform Architecture.pdf](docs/architecture/Protocol-Mediated%20Agentic%20Money%20Movement%20Control%20Platform%20Architecture.pdf) into a proof-of-concept repository shape.

The PoC is intentionally narrow:

- One domestic payment workflow: draft -> validate -> approval -> release -> settlement pending.
- One execution adapter: a mock domestic rail behind the capability gateway.
- One deterministic policy path: OPA decides whether the action is allowed, denied, or escalated.
- One durable workflow path: Temporal owns state transitions and replay.
- One async transport: NATS handles events for approvals, release updates, and reconciliation signals.

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
  orchestrator-api/     intake API, registry lookups, policy checks, workflow kickoff, MCP server adapter
  policy-service/       OPA bundle and policy-service notes
  capability-gateway/   typed wrappers around mock payment rails
services/
  workflow-worker/      Temporal workflows and activities
  event-consumer/       async event handlers and read model updates
  memory-service/       task state, provenance, and retrieval boundary
packages/
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
2. It loads registries and current task context from `memory-service`.
3. It calls OPA with explicit action, amount, rail, beneficiary status, and task-scoped scopes.
4. If allowed, `workflow-worker` drives validation, approval wait states, release, and ambiguous-response holds.
5. `capability-gateway` talks to a mock rail and emits structured events.
6. `event-consumer` updates read models and audit projections.

## Current Implemented Slice

The PoC currently includes:

- `memory-service` as the durable task state and provenance boundary.
- `orchestrator-api` as both a REST intake API and an MCP server adapter.
- `workflow-worker` as the service that advances validation, approval wait states, and release.
- MCP tools, resources, and a review prompt exposed through the orchestrator for controlled task creation and retrieval.

For service-level run commands and MCP details, see [apps/orchestrator-api/README.md](apps/orchestrator-api/README.md).
