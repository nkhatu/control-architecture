# Implementation Update: Protocol-Mediated Agentic Money Movement Control Platform

This document updates the architecture described in [Protocol-Mediated Agentic Money Movement Control Platform Architecture.pdf](./Protocol-Mediated%20Agentic%20Money%20Movement%20Control%20Platform%20Architecture.pdf) based on what is actually implemented in the repository as of March 22, 2026.

It is not a replacement for the original PDF. It is an implementation-facing addendum that answers three practical questions:

1. What parts of the architecture are now built?
2. Where has the implementation evolved beyond the original repository shape in the PDF?
3. Which gaps still separate the PoC from the full target architecture?

## Executive Summary

The repository now materially implements the architecture’s core thesis:

- control, policy, capability execution, workflow, and state are separated
- the state boundary is split into `context-memory-service` and `provenance-service`
- an outbox/event-consumer path keeps current state and provenance aligned
- `orchestrator-api` exposes both REST and MCP entry points
- delegated-agent runtime exists for beneficiary validation and approval routing
- `ops-console` is now a usable operator surface, including trust-graph-driven navigation

The strongest implemented areas are:

- explicit control separation
- typed capability design
- explicit workflow state and durable provenance
- delegated agent tracking
- image- and document-aligned operator workflows

The biggest remaining gaps are:

- no write path yet for `control-plane`
- no real OPA bundle/data execution path yet in `policy-engine`
- no Temporal-native runtime yet for `workflow-worker`
- no broker-backed event delivery for the broader workflow surface
- no production-grade auth, delegated token enforcement, or anomaly detection
- no real external rail or bank integration beyond the mock adapter
- observability and security hardening remain partial

## Section-by-Section Update To The PDF

## 3. Control Plane Design

### What is built

- A real read-only `control-plane` runtime exists under `apps/control-plane`.
- It publishes the active control-plane document, capability registry, agent registry, summary values, and snapshot/version metadata.
- `orchestrator-api`, `policy-engine`, `workflow-worker`, and `capability-gateway` now consume `control-plane` first and use local file fallback only for isolated development or tests.

### What should be updated in the PDF

- The document should no longer describe the control plane as only a design target. It now exists as a runtime boundary in the PoC.
- The repository naming should be updated from `policy-service` to `policy-engine` and from `control-plane-service` to `control-plane`.
- The control-plane implementation should be described as read-only today, with consumer migration largely complete.

### Gaps

- No write API for control updates.
- No approval workflow for control-plane changes.
- No persisted audit/version control for changes to thresholds, kill switch, or registry entries.
- No control-plane-signed distribution model yet.

## 4. Capability Surface Design

### What is built

- `capability-gateway` implements typed mock-rail capabilities for:
  - payment instruction creation
  - beneficiary validation
  - approval-backed release
  - payment status lookup
- Capability registry data exists in `config/registry/capabilities.yaml`.
- Capability behavior includes side-effect classes and idempotency-aware release handling.
- The PoC supports deterministic success, reject, and ambiguous release outcomes.

### What should be updated in the PDF

- The capability surface is no longer abstract; a working typed wrapper layer exists.
- The document should explicitly call out that the current implementation uses a mock domestic rail for execution.
- The repository includes shared JSON Schema contracts in `packages/capability-schemas` and typed Python runtime contracts in `packages/shared-contracts`.

### Gaps

- No real bank or payment-rail adapter yet.
- No cancel capability yet in the current PoC slice.
- No richer discovery or health-based runtime capability selection beyond the registry snapshot.
- No fully transport-independent invocation layer yet; calls are still local HTTP between services.

## 5. Context And Memory Design

### What is built

- The original single `memory-service` architecture has been intentionally split into:
  - `context-memory-service`
  - `provenance-service`
- `context-memory-service` owns the current task snapshot.
- `provenance-service` owns state transitions, artifacts, provenance, and delegated work.
- `event-consumer` projects outbox events from context into provenance.
- Shared task read models are exposed through typed contracts in `packages/shared-contracts`.

### What should be updated in the PDF

- Section 5 should explicitly describe the split state boundary instead of a single memory layer implementation.
- The architecture should mention transactional outbox projection between current state and provenance as the current PoC consistency mechanism.
- The repository layout in the document should be revised to reflect the split memory boundary and the added projection service.

### Gaps

- Event-driven projection is implemented for task creation and state changes, but not yet for every provenance record type.
- The delegation lifecycle in the code is narrower than the full model in the PDF.
- Current delegation statuses are closer to `queued`, `pending`, `completed`, `failed`, and `cancelled` than to the full `offered -> accepted -> in_progress -> waiting_on_dependency -> completed` model.
- Full Postgres-backed operational hardening is still partial.

## 5.1 State And Status Model

### What is built

- Task lifecycle statuses are modeled in shared contracts and service schemas:
  - `received`
  - `validated`
  - `awaiting_approval`
  - `approved`
  - `released`
  - `settlement_pending`
  - `settled`
  - `failed`
  - `cancelled`
  - `pending_reconcile`
  - `exception`
- The happy path currently exercises:
  - `received`
  - `awaiting_approval`
  - `approved`
  - `released`
  - `settlement_pending`
  - `pending_reconcile`
  - `failed`
  - `exception`

### Gaps

- `settled` and `cancelled` exist in the type system but are not yet fully implemented as active runtime flows.
- The reference workflow is stronger than the original early scaffold, but still narrower than the full lifecycle imagined in the PDF.

## 6. Protocol And Interoperability Layer

### What is built

- `orchestrator-api` now includes a real MCP server adapter.
- MCP tools, resources, and prompts are exposed for controlled orchestration.
- The repo includes a common message envelope schema in `packages/capability-schemas`.
- Shared typed runtime envelope models now exist for delegated work and artifact payloads.
- Capability and agent registries exist and are consumed by runtime services.

### What should be updated in the PDF

- The PDF should explicitly note that the PoC has already crossed from “protocol-aware design” into an initial MCP implementation.
- The reference implementation section should mention the existing MCP adapter rather than only describing it conceptually.
- The document should clarify that protocol participation is present today via MCP, but not yet across the broader A2A / ACP / SLIM transport matrix.

### Gaps

- No true A2A or ACP runtime yet.
- No SLIM-like transport layer or transport abstraction implementation yet.
- No version negotiation or compatibility enforcement for contracts at runtime.
- Most service-to-service communication is still direct HTTP.

## 7. Protocol Interoperability Reference Model

### What is built

- The common message envelope exists as a schema artifact.
- Agent registry and capability registry are implemented in YAML and published through `control-plane`.
- Parent/delegated-agent execution exists for compliance screening and approval routing.
- Request/response envelopes and delegated work records are persisted in provenance.

### What should be updated in the PDF

- The `Agent card` and `Delegation contract` sections should note that these are partially modeled and partially implemented, not purely conceptual.
- The reference model should reflect that:
  - `agent.payment_orchestrator` acts as the parent agent
  - `agent.compliance_screening` handles beneficiary validation
  - `agent.approval_router` handles approval routing
- The repository now includes both schema-level and Python-runtime versions of the same contract families.

### Gaps

- Delegated authorization tokens are not yet enforced as real scoped credentials.
- Identity preservation is modeled, but not yet backed by signed delegated tokens.
- The trust-tier model exists in config and documentation, but runtime authorization remains partial.

## 8. Security Posture

### What is built

- Deterministic policy checks are outside the model.
- Provenance and workflow lineage are materially stronger than a prompt-based architecture.
- Approval-backed release is enforced in the current flow.
- Ambiguous release outcomes degrade to safe states like `pending_reconcile`.

### What should be updated in the PDF

- The document should recognize that the platform already has meaningful guardrails for:
  - approval gating
  - idempotency-aware release
  - provenance capture
  - bounded delegated execution

### Gaps

- No JWT signing and verification flow in the running stack yet.
- No delegated token narrowing enforcement yet.
- No anomaly detection pipeline.
- No prompt-isolation or side-effect sandbox implementation beyond basic architectural boundaries.
- No mTLS or production-grade internal identity model.

## 8.1 Provenance Requirements

### What is built

- Provenance is now a first-class service boundary.
- The PoC preserves:
  - initiating user
  - last updater
  - trace identifiers
  - policy artifacts
  - delegated request and response envelopes
  - state transition history
  - release results

### Gaps

- Not every provenance class is projected by the outbox path yet.
- Operator-facing provenance explanation is present in the task explorer, but observability-grade audit streaming is not yet implemented.

## 8.2 Policy Checkpoints

### What is built

- `policy-engine` performs intake and release decisions.
- Release checks include:
  - current state
  - beneficiary approval state
  - human approval result
  - release control configuration
- `orchestrator-api` now routes through `policy-engine` instead of making local policy decisions.

### Gaps

- The engine is deterministic and control-plane-backed, but not yet backed by real OPA bundle/data execution.
- Risk checks remain shallow compared to the full policy checkpoint list in the PDF.
- No device/channel or anomaly scoring controls yet.

## 8.3 Trust Graph Model

### What is built

- The trust graph is no longer only documentation:
  - parent agent is explicit
  - delegated agents are explicit
  - context memory is explicit
  - provenance is explicit
  - capability invocation is explicit
- The `ops-console` now includes a trust-graph navigation page that maps architecture elements to operator views.

### Gaps

- Runtime trust-graph evaluation by the control plane is not yet implemented as a first-class decision engine.
- The graph is reflected in the architecture and UX, but not yet in a formal runtime graph evaluator.

## 8. Reference Workflow: Domestic Payment Release

### What is built

- The PoC supports the intended narrow domestic workflow:
  - intake
  - validation
  - approval wait
  - approval resume
  - release
  - settlement pending or pending reconcile
- `workflow-worker` owns the execution path rather than `orchestrator-api`.
- Approval resume completes the pending delegated approval-routing record before release continues.

### What should be updated in the PDF

- The workflow section should note that the PoC is beyond pure intake and already executes a bounded end-to-end release path.
- The document should call out that ambiguous downstream results currently map to `pending_reconcile`.

### Gaps

- No true settlement-confirmed flow to `settled` yet.
- No cancellation flow yet.
- No real downstream callbacks or reconciliation fan-out yet.

## 9. Operating Model And Observability

### What is built

- The repo has placeholder observability packaging and structured contract boundaries.
- Tests now cover policy, workflow, gateway, MCP, projection, and service loaders.

### Gaps

- No OpenTelemetry implementation.
- No Prometheus / Grafana dashboards.
- No approval-latency or per-rail runtime dashboards.
- No strong production observability posture yet.

## 10. Non-Functional Requirements

### What is built

- Idempotency is enforced at the mock release boundary.
- Workflow history is explicit and queryable.
- Progressive containment is partially reflected through `dry_run` mode and control-plane-backed release settings.

### Gaps

- Queueing and latency classes are not yet formalized.
- Replayability is present in workflow shape and provenance, but not yet through Temporal-native execution.
- Broader containment modes remain mostly configuration-level rather than fully operational.

## 11. Reference Technology Stack

### Actual PoC stack today

The PDF’s target stack should be updated with what is currently implemented:

- UI + ops console: React + Vite, not Next.js
- Orchestrator: Python FastAPI
- Policy: Python FastAPI `policy-engine` with OPA-aligned control model, not yet true OPA execution
- Workflow: Python FastAPI worker with local HTTP orchestration, not yet Temporal-native runtime
- Context/provenance: split Python services backed by SQLite in the fastest local path
- Event projection: local outbox consumer, not yet Kafka/NATS-backed for the broad workflow
- Control plane: read-only FastAPI service publishing control and registry snapshots

### Gaps

- No Kong / Apigee layer.
- No production secrets / identity stack.
- No real vector store or richer memory retrieval layer.
- Temporal, NATS, Redis, Postgres, and OPA exist in local scaffolding but are not yet the dominant runtime path for the full flow.

## 12. Key Configuration Model

### What is built

- Control-plane config exists in `config/control-plane/default.yaml`.
- Registry config exists in `config/registry/capabilities.yaml` and `config/registry/agents.yaml`.
- Runtime services read `control-plane` over HTTP first.

### What should be updated in the PDF

- The key configuration model is no longer hypothetical. It exists and is actively consumed.
- The document should mention snapshot/version publication as part of the control-plane runtime.

### Gaps

- No versioned config write path yet.
- No approval/audit workflow for config changes.
- Some advanced security and observability config remains declarative rather than enforced.

## 13. Repository And Code Setup

### What is built

The repository now diverges from the original example in important ways:

```text
apps/
  ops-console/
  control-plane/
  orchestrator-api/
  policy-engine/
  capability-gateway/
services/
  context-memory-service/
  provenance-service/
  workflow-worker/
  event-consumer/
packages/
  shared-contracts/
  capability-schemas/
  policy-models/
  security-middleware/
  observability/
config/
  control-plane/
  registry/
docs/
  architecture/
  runbooks/
  threat-models/
```

### What should be updated in the PDF

- Replace `policy-service` with `policy-engine`.
- Replace `memory-service` with `context-memory-service` plus `provenance-service`.
- Add `control-plane`.
- Add `shared-contracts`.
- Update the repository setup section to reflect the built `ops-console` and the new install/runbook material.

### Gaps

- The repo is ahead of the PDF in structure, but still behind the target runtime architecture in a few critical areas:
  - Temporal-native workers
  - broker-backed message delivery
  - production auth/security middleware

## 14. Example Service Contracts

### What is built

- Real service contracts now exist for:
  - task intake
  - task resume
  - beneficiary validation
  - payment release
  - task state projection
  - provenance writes
  - MCP tool/resource access

### What should be updated in the PDF

- The service contract section should add examples from:
  - `orchestrator-api`
  - `capability-gateway`
  - `workflow-worker`
  - `context-memory-service`
  - `provenance-service`

### Gaps

- Contract examples in the PDF still read as representative pseudocode, while the repo now contains runnable service contracts and tests.
- More of those concrete examples should be reflected in the architecture appendix.

## 15. Implementation Roadmap

### Completed or materially advanced

- Phase 1 is effectively achieved:
  - typed capabilities
  - explicit workflow state
  - deterministic control plane around a narrow domestic use case
- Phase 2 is partially achieved:
  - protocol-mediated tool access via MCP
  - structured approval workflows
  - better operator tooling
- Phase 3 is only partially started:
  - specialized agents exist
  - delegated runtime exists
  - stronger runtime security controls are still mostly future work

### Recommended next priorities

1. Add a write path and audit model for `control-plane`.
2. Move `policy-engine` from OPA-aligned logic to actual OPA-backed decisioning.
3. Move `workflow-worker` to Temporal-native execution.
4. Expand outbox/event projection beyond task create and state change.
5. Implement delegated token validation and scoped authority enforcement.
6. Add observability and runtime security controls before expanding execution authority.

## Gap Matrix

| Area | Implemented | Partial | Gap |
| --- | --- | --- | --- |
| Control-plane runtime | Yes | Read-only only | No control write path or change governance |
| Policy boundary outside the model | Yes | Deterministic only | No real OPA bundle execution |
| Typed capability surface | Yes | Mock rail only | No real bank/rail integration |
| Split task state and provenance | Yes | Projection scope limited | Not all provenance classes projected asynchronously |
| Delegated-agent runtime | Yes | Narrow slice only | No broader multi-agent task families |
| MCP interoperability | Yes | Orchestrator-focused | No A2A / ACP / SLIM runtime |
| Temporal workflow engine | No | Local HTTP worker only | No durable workflow engine in the active path |
| Broker-backed messaging | No | Local outbox consumer only | No NATS/Kafka-driven runtime for the broader flow |
| Security posture | Partial | Basic policy/provenance in place | No delegated tokens, anomaly scoring, mTLS, or strong IAM |
| Observability | Partial | Tests and structure exist | No OpenTelemetry dashboards or production telemetry |
| Ops console | Yes | Early operator slice | No server-side queueing, auth, or deeper investigation tooling |

## Conclusion

The PoC is no longer just a repository scaffold. It now implements the architecture’s central separation pattern in runnable form:

- control-plane
- policy engine
- capability gateway
- orchestrator
- workflow worker
- split current-state and provenance boundaries
- event-driven state/provenance reconciliation
- delegated-agent runtime
- operator console

The architecture document should now be updated to acknowledge that the project has moved from conceptual design into an executable constrained slice. The next revision of the PDF should focus less on repository intent and more on the remaining production gaps:

- control-plane governance
- real policy-engine execution
- durable workflow/runtime infrastructure
- production security enforcement
- observability
- real rail integration
