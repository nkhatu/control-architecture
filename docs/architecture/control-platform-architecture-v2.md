---
title: "Protocol-Mediated Agentic Domestic Money Movement Control Platform"
subtitle: "Consolidated Architecture v2"
author: "Neil Khatu"
date: "March 22, 2026"
---

# Protocol-Mediated Agentic Domestic Money Movement Control Platform

## Consolidated Architecture v2

This document consolidates the original architecture in [Protocol-Mediated Agentic Money Movement Control Platform Architecture.pdf](./Protocol-Mediated%20Agentic%20Money%20Movement%20Control%20Platform%20Architecture.pdf) with the implementation corrections in [implementation-update-2026-03.md](./implementation-update-2026-03.md).

It is intended to replace the earlier "original PDF plus addendum" reading experience with one architecture narrative that is aligned to the current repository.

Source inputs:

- [Protocol-Mediated Agentic Money Movement Control Platform Architecture.pdf](./Protocol-Mediated%20Agentic%20Money%20Movement%20Control%20Platform%20Architecture.pdf)
- [implementation-update-2026-03.md](./implementation-update-2026-03.md)

\newpage

## Table Of Contents

1. [Scope And Business Boundary](#1-scope-and-business-boundary)
2. [Expanded Design Principles](#2-expanded-design-principles)
3. [Control Plane Design](#3-control-plane-design)
4. [Capability Surface Design](#4-capability-surface-design)
5. [Context, Memory, And Provenance Design](#5-context-memory-and-provenance-design)
6. [Protocol And Interoperability Layer](#6-protocol-and-interoperability-layer)
7. [Protocol Interoperability Reference Model](#7-protocol-interoperability-reference-model)
8. [Security Posture](#8-security-posture)
9. [Reference Workflow: Domestic Payment Release](#9-reference-workflow-domestic-payment-release)
10. [Operating Model And Observability](#10-operating-model-and-observability)
11. [Non-Functional Requirements](#11-non-functional-requirements)
12. [Reference Technology Stack](#12-reference-technology-stack)
13. [Key Configuration Model](#13-key-configuration-model)
14. [Repository And Code Setup](#14-repository-and-code-setup)
15. [Example Service Contracts](#15-example-service-contracts)
16. [Implementation Roadmap](#16-implementation-roadmap)
17. [Conclusion](#17-conclusion)
18. [Appendix A: Architecture Readiness Checklist](#appendix-a-architecture-readiness-checklist)

\newpage

# 1. Scope And Business Boundary

This architecture remains intentionally bounded to domestic money movement. The active proof of concept covers:

- customer-initiated or operator-assisted domestic payment intake
- beneficiary validation
- approval routing
- approval-backed release
- payment-status inquiry
- exception visibility
- provenance capture

It still does not attempt to solve, end to end:

- international wires and FX
- card processing
- full sanctions-policy authoring
- core ledger architecture
- production settlement reconciliation across multiple bank systems

That bounded scope is still correct. Domestic money movement is narrow enough to make control failures visible, yet high-stakes enough that state ambiguity, weak identity propagation, and vague capability contracts immediately become operational risk.

Current implementation alignment:

- The repository now materially executes a narrow domestic path rather than only describing one.
- The active happy path is intake -> validation -> awaiting approval -> approval resume -> release -> settlement pending or pending reconcile.
- The execution surface is still mock-rail based, so this remains a control-pattern proof of concept, not a production payment platform.

Primary business thesis:

- policy, action, state, provenance, and delegation must stay separate
- irreversible financial effects must be policy-gated and idempotent
- models may recommend, but deterministic systems must decide and execute

\newpage

# 2. Expanded Design Principles

The original principles still hold, but the implementation now lets us restate them as architectural rules rather than aspirations.

| Principle | What it means in this repository |
| --- | --- |
| Controls outside the model | `policy-engine` and `control-plane` determine whether intake and release proceed. |
| Typed capabilities over vague endpoints | `capability-gateway` exposes explicit operations such as instruction creation, beneficiary validation, release, and status lookup. |
| State as a first-class asset | Current state is durable in `context-memory-service`; provenance and delegated work are durable in `provenance-service`. |
| Least privilege by task and time | Delegation is parent-agent bounded and task-scoped, although real delegated token enforcement is still a gap. |
| Safe failure over speculative completion | Ambiguous release outcomes degrade to `pending_reconcile` instead of optimistic success. |
| Idempotency at money-movement boundaries | Release handling in `capability-gateway` is idempotency-aware. |
| Provenance by default | User identity, agent identity, state changes, artifacts, delegation envelopes, and release results are persisted. |
| Trust-tiered memory | Task state and provenance are separated; external content is not blended into a single prompt-only memory surface. |
| Protocol-aware but policy-led | `orchestrator-api` exposes MCP, but policy still sits outside protocol transport. |
| Human override for irreversible outcomes | Approval-backed resume is required before release continues. |
| Observability as an operating requirement | The repo has structured boundaries and test coverage, but production-grade telemetry is still incomplete. |
| Progressive containment | The design supports safe states, dry-run style control modes, and a read-only control plane before broader rollout. |

Design consequences that are now visible in code:

1. "Memory" is no longer treated as one generic store.
2. Orchestration is not allowed to execute payment release directly.
3. Approval routing is modeled as delegated work, not as an inlined orchestrator detail.
4. Configuration publication and policy evaluation are split from execution services.

\newpage

# 3. Control Plane Design

The control plane is now a real runtime boundary, not just a design concept.

Purpose:

- publish the active control-plane snapshot
- publish the capability registry
- publish the agent registry
- provide a single runtime read source for consumers
- expose version and digest metadata so consumers can reason about what configuration they are using

Current implementation:

- App: `apps/control-plane`
- Runtime type: FastAPI service
- Current mode: read-only
- Consumers: `orchestrator-api`, `policy-engine`, `workflow-worker`, and `capability-gateway`

Published views:

- full control-plane document
- capabilities registry
- agents registry
- control summary
- current version metadata
- combined snapshot digest

Control domains reflected today:

| Domain | Current status |
| --- | --- |
| Identity and principal context | Partial, modeled in workflow and provenance |
| Policy thresholds | Built and published |
| Approval requirements | Built in config and enforced through `policy-engine` |
| Rail and amount controls | Built in config and consumed by runtime services |
| Kill-switch posture | Published in the control-plane summary |
| Registry publication | Built |

What is still missing:

- write APIs for control changes
- approval workflow for control changes
- persisted configuration governance and audit
- signed or version-pinned distribution enforcement
- runtime consumer pinning to an approved snapshot instead of best-effort latest-plus-fallback behavior

Architecture guidance:

- `control-plane` should remain the publishing authority for policy, registries, and operational control configuration
- decision execution should remain in `policy-engine`
- operational state should remain outside the control plane

\newpage

# 4. Capability Surface Design

The capability surface is the machine-usable boundary that agents and orchestrators invoke. In the current implementation, that boundary is concentrated in `capability-gateway`.

Implemented capabilities:

| Capability | Type | Side effect | Current implementation |
| --- | --- | --- | --- |
| Create domestic payment instruction | Draft | None | Built |
| Validate beneficiary | Validation | None | Built |
| Release payment | Execution | Financial side effect | Built with deterministic mock outcomes |
| Get payment status | Inquiry | None | Built |

The current capability model is stronger than the original scaffold in three ways:

1. Capabilities are typed and narrow.
2. Release behavior carries idempotency and side-effect semantics.
3. The mock rail can simulate `success`, `reject`, and `ambiguous` outcomes, which gives the workflow meaningful control behavior to respond to.

Registry role:

- The capability registry remains the machine-readable directory of what can be called.
- `control-plane` now publishes that registry as a runtime snapshot.
- `orchestrator-api` and related services can reason about capabilities from the same source instead of loading independent local files by default.

Current gaps:

- no real bank or payment-rail integration
- no cancellation capability in the active flow
- no dynamic health-based routing across multiple providers
- service-to-service invocation is still local HTTP rather than transport-abstracted runtime invocation

Target architectural rule:

- capabilities should continue to describe preconditions, scopes, side effects, idempotency, timeouts, and failure semantics explicitly
- payment release must remain a narrow capability and must not collapse into a generic "process payment" endpoint

\newpage

# 5. Context, Memory, And Provenance Design

The architecture has evolved beyond the original "memory-service" shape. The current proof of concept intentionally splits current state from evidence and lineage.

Current service boundaries:

| Boundary | Responsibility |
| --- | --- |
| `context-memory-service` | Current task snapshot and outbox events |
| `provenance-service` | State history, artifacts, provenance records, and delegated work |
| `event-consumer` | Projects outbox events from context into provenance |

This split is cleaner for both architecture and operations:

- current state stays query-friendly and operational
- provenance remains append-oriented and evidence-friendly
- reconciliation between the two is explicit rather than implicit

Current memory classes in practice:

| Class | Examples | Current home |
| --- | --- | --- |
| Task state | amount, rail, customer, approval status, beneficiary status, workflow status | `context-memory-service` |
| Provenance | initiator, trace ID, last updater, policy artifacts, release artifacts | `provenance-service` |
| Delegated work | parent agent, delegated agent, action, request envelope, result envelope, lifecycle status | `provenance-service` |
| Registry and policy context | thresholds, registries, release controls | `control-plane` and `policy-engine` |

State model:

- The task lifecycle is explicit and typed.
- The active slice exercises `received`, `awaiting_approval`, `approved`, `released`, `settlement_pending`, `pending_reconcile`, `failed`, and `exception`.
- `settled` and `cancelled` exist in the type system but are not yet full active flows in the running slice.

Delegation model:

- `agent.payment_orchestrator` acts as the parent agent.
- `agent.compliance_screening` handles beneficiary validation.
- `agent.approval_router` handles approval routing.
- approval resume completes the pending delegated approval-routing record before release continues.

Consistency model:

- `context-memory-service` writes outbox events in the same transaction as task-state changes
- `event-consumer` projects those events into `provenance-service`
- current implementation covers task creation and state changes

Gaps:

- not every provenance class is projected asynchronously yet
- broader event-driven projection for artifacts and delegation changes remains unfinished
- the delegation status model is narrower than the full conceptual lifecycle in the original document

\newpage

# 6. Protocol And Interoperability Layer

The architecture is no longer only "protocol-aware." It now has a concrete MCP-facing slice.

Current protocol role:

- `orchestrator-api` exposes REST for operational integration
- `orchestrator-api` also exposes MCP for tool/resource/prompt style orchestration access
- shared message-envelope concepts exist in both JSON Schema and Python runtime form

Implemented protocol assets:

| Asset | Current status |
| --- | --- |
| MCP server adapter | Built |
| Common message envelope schema | Built |
| Typed runtime delegation envelopes | Built |
| Capability registry publication | Built |
| Agent registry publication | Built |
| MCP tools/resources/prompts for orchestrator | Built |

What this layer does:

- standardizes machine-readable access to orchestration capabilities
- preserves task, trace, and delegation metadata across orchestration boundaries
- keeps protocol participation subordinate to deterministic policy

What it does not do:

- decide policy
- replace workflow state
- own payment-domain execution logic

Current gaps:

- no A2A runtime beyond local delegated workflow behavior
- no ACP runtime
- no SLIM-like transport abstraction
- little runtime contract negotiation beyond static compatibility
- most service-to-service communication is still plain local HTTP

Architectural direction:

- keep MCP as the first implemented protocol surface
- add broader inter-agent transport only after policy, identity, and state boundaries are strong enough to support it safely

\newpage

# 7. Protocol Interoperability Reference Model

The reference model should now be described as partially implemented instead of purely aspirational.

Canonical concepts already represented:

| Concept | Current implementation status |
| --- | --- |
| Common message envelope | Schema-level and runtime models exist |
| Capability descriptor | Registry-driven and published through `control-plane` |
| Agent card / agent metadata | Registry-driven and published through `control-plane` |
| Delegation contract | Persisted through delegated work records |
| Parent/delegated roles | Implemented in the workflow slice |
| Trust metadata | Modeled in schemas and provenance |

Current role mapping:

| Role | Current implementation |
| --- | --- |
| Human initiator | User identity persisted in provenance |
| Parent agent | `agent.payment_orchestrator` |
| Delegated validation agent | `agent.compliance_screening` |
| Delegated approval agent | `agent.approval_router` |
| Executing capability surface | `capability-gateway` |

Important current truth:

- identity preservation is modeled and persisted
- true delegated authorization tokens are not yet enforced as signed scoped credentials
- transport-neutral contracts exist more strongly than transport-neutral runtime behavior

Reference-model gaps to carry forward:

- signed delegated token enforcement
- trust-tier enforcement beyond documentation and configuration
- runtime compatibility negotiation and retirement enforcement
- broader inter-agent discovery beyond static registry publication

\newpage

# 8. Security Posture

The security posture is materially better than a prompt-only agent architecture, but it is still not production-grade.

Controls already present:

| Control | Current status |
| --- | --- |
| Deterministic policy outside the model | Built |
| Approval gate before release | Built |
| Provenance and lineage capture | Built |
| Idempotency-aware release behavior | Built |
| Safe ambiguous-outcome handling | Built |
| Bounded delegated workflow roles | Built, but without real delegated credentials |

Security posture by area:

## 8.1 Provenance Requirements

The proof of concept now preserves:

- initiating user
- parent agent
- delegated agents
- state transitions
- artifacts such as policy decisions and release results
- trace and correlation context

Provenance is now a first-class service boundary through `provenance-service`.

## 8.2 Policy Checkpoints

`policy-engine` currently performs:

- intake decisioning
- release decisioning
- control-plane-backed threshold and rule evaluation

This keeps policy out of the model and out of the protocol layer, which matches the original architectural intent.

## 8.3 Trust Graph Model

The trust graph is now reflected in both runtime structure and operator tooling:

- parent agent and delegated agents are explicit in the workflow
- context memory and provenance are separate boundaries
- capability invocation is explicit
- `ops-console` includes a trust-graph navigation page

## 8.4 Operational Guidance

The design still assumes that irreversible actions must remain:

- policy-gated
- human-approval-aware
- idempotent
- reconstructable after the fact

Major gaps:

- no signed JWT or delegated token validation flow
- no mTLS or strong service identity model
- no anomaly-detection or device/channel risk layer
- no production-grade secret distribution model
- no prompt-sandbox or tool-execution hardening beyond the current architectural separation

\newpage

# 9. Reference Workflow: Domestic Payment Release

The reference workflow is now implemented as a narrow runnable slice.

Current flow:

1. A user initiates a domestic payment request through `orchestrator-api`.
2. `orchestrator-api` asks `policy-engine` for an intake decision.
3. If allowed, `workflow-worker` creates the draft instruction through `capability-gateway`.
4. The worker delegates beneficiary validation to `agent.compliance_screening`.
5. The worker delegates approval routing to `agent.approval_router`.
6. The task transitions to `awaiting_approval`.
7. An operator resumes the task after approval through `orchestrator-api` or the `ops-console`.
8. `orchestrator-api` requests a release decision from `policy-engine`.
9. If allowed, `workflow-worker` completes the pending approval delegation and invokes release through `capability-gateway`.
10. The task ends in `settlement_pending`, `pending_reconcile`, `failed`, or `exception`, depending on the outcome.

What is working now:

- approval wait and approval resume are real
- release is owned by the worker, not the API
- ambiguous downstream results degrade to a safe state
- state and provenance remain queryable throughout the flow

What is not built yet:

- terminal settlement-confirmed progression to `settled`
- cancellation flow
- real bank callback handling
- broader reconciliation event fan-out

\newpage

# 10. Operating Model And Observability

The operating model is present in structure more than in full telemetry.

What exists now:

- explicit service boundaries
- control, policy, workflow, state, and provenance separation
- operator UI via `ops-console`
- end-to-end and focused automated tests
- service health endpoints
- provenance-rich task exploration in the UI

What is still missing:

- OpenTelemetry tracing
- Prometheus metrics
- Grafana dashboards
- rail-specific latency and failure dashboards
- approval-latency and exception queue analytics
- streamed audit export for external observability systems

Operational posture today:

- strong enough for a constrained PoC
- not yet strong enough for a production operating model

\newpage

# 11. Non-Functional Requirements

The non-functional story is partly implemented and partly still target-state.

Implemented characteristics:

| Requirement | Current status |
| --- | --- |
| Explicit durable workflow state | Built |
| Idempotency at release boundary | Built |
| Safe degradation on ambiguous release | Built |
| Testable deterministic behavior | Built |
| Progressive containment | Partial |

Still incomplete:

- durable workflow replay under a workflow engine
- formal latency classes and SLOs
- large-scale async delivery behavior
- resource and throughput governance beyond the current narrow path
- production containment and downgrade procedures

Assessment:

The PoC already demonstrates the right quality shape: explicit state, bounded side effects, and safe failure. The remaining work is mainly runtime-hardening and operationalization.

\newpage

# 12. Reference Technology Stack

The current proof of concept differs from the original target stack in several important ways. This section should be treated as the implemented stack, not the aspirational stack.

| Layer | Implemented PoC stack | Notes |
| --- | --- | --- |
| Operator UI | React + Vite | `ops-console`, not Next.js |
| Orchestration API | Python + FastAPI | `orchestrator-api` with REST + MCP |
| Control publication | Python + FastAPI | `control-plane`, currently read-only |
| Policy runtime | Python + FastAPI | `policy-engine`, deterministic and OPA-aligned but not true OPA-backed yet |
| Workflow runtime | Python + FastAPI | `workflow-worker`, not Temporal-native in the active path |
| Capability runtime | Python + FastAPI | `capability-gateway` with mock rail |
| Current state | SQLAlchemy-backed service | `context-memory-service` |
| Provenance | SQLAlchemy-backed service | `provenance-service` |
| Event projection | Local outbox consumer | `event-consumer` |
| Shared runtime contracts | Pydantic models | `packages/shared-contracts` |
| Language-neutral contracts | JSON Schema | `packages/capability-schemas` |

Local infrastructure scaffolding exists for stronger components such as Postgres, OPA, NATS, Redis, and Temporal, but those are not yet the dominant active runtime for the end-to-end slice.

\newpage

# 13. Key Configuration Model

Configuration is no longer hypothetical. It is present as runtime-consumable control data and registry data.

Current configuration sources:

| Source | Purpose |
| --- | --- |
| `config/control-plane/default.yaml` | Core control settings |
| `config/registry/capabilities.yaml` | Capability registry |
| `config/registry/agents.yaml` | Agent registry |

Current runtime behavior:

- `control-plane` publishes the merged runtime snapshot
- `orchestrator-api`, `policy-engine`, `workflow-worker`, and `capability-gateway` consume that snapshot first
- local file fallback remains available for isolated development and testing

Current configuration gaps:

- no write path
- no approval flow for change management
- no version-pinned rollout workflow
- no signed snapshot distribution
- advanced security and observability settings remain more declarative than enforced

\newpage

# 14. Repository And Code Setup

The repository structure has evolved beyond the original document and should be reflected directly in the architecture.

```text
apps/
  capability-gateway/
  control-plane/
  ops-console/
  orchestrator-api/
  policy-engine/
services/
  context-memory-service/
  event-consumer/
  provenance-service/
  workflow-worker/
packages/
  capability-schemas/
  observability/
  policy-models/
  security-middleware/
  shared-contracts/
config/
  control-plane/
  registry/
docs/
  architecture/
  runbooks/
  threat-models/
```

Naming corrections relative to the earlier document:

- `control-plane-service` is now `control-plane`
- `policy-service` is now `policy-engine`
- `memory-service` has been split into `context-memory-service` and `provenance-service`

Documentation now available in-repo:

- root `README.md`
- root `INSTALL.md`
- local setup runbook
- install-from-GitHub runbook
- end-to-end testing runbook
- implementation update addendum

\newpage

# 15. Example Service Contracts

The repository now contains real runnable service contracts rather than only representative pseudocode.

Representative contract families:

| Boundary | Example contracts |
| --- | --- |
| `orchestrator-api` | create domestic payment task, resume task, get task |
| `capability-gateway` | create instruction, validate beneficiary, release payment, get status |
| `workflow-worker` | start workflow, resume after approval |
| `context-memory-service` | create task, patch task state, get task, outbox projection source |
| `provenance-service` | write artifacts, persist delegations, read task evidence |
| MCP surface | list tools, call tool, read resource, get prompt |

Contract separation model:

- Python-native runtime contracts live in `packages/shared-contracts`
- language-neutral JSON Schema contracts live in `packages/capability-schemas`
- service-local command schemas stay inside their service boundaries

That separation is important because it keeps:

- transport-level contracts explicit
- runtime model reuse manageable
- cross-service drift visible and reviewable

Remaining gaps:

- some transport DTOs are still local to service clients and can be tightened further
- real external-rail contracts do not exist yet because the current capability surface still uses a mock rail

\newpage

# 16. Implementation Roadmap

The roadmap should now distinguish between what is already built, what is partially built, and what remains architecturally necessary before this pattern can be called production-shaped.

## 16.1 Built Or Materially Advanced

- read-only `control-plane`
- `policy-engine` as a deterministic policy boundary
- `orchestrator-api` with REST and MCP
- `capability-gateway`
- `workflow-worker`
- split current-state and provenance services
- outbox-driven projection for key state changes
- delegated-agent runtime for validation and approval routing
- `ops-console` with trust-graph-driven navigation

## 16.2 Highest-Priority Remaining Work

1. Add a write path, versioning model, and governance flow to `control-plane`.
2. Move `policy-engine` from OPA-aligned logic to actual OPA-backed evaluation.
3. Move `workflow-worker` to Temporal-native execution.
4. Expand event-driven projection beyond task create and state change.
5. Add delegated token validation and stronger scoped identity enforcement.
6. Add real observability and runtime security controls.
7. Replace the mock rail with a real external integration boundary.

## 16.3 Gap Matrix

| Area | Implemented | Partial | Gap |
| --- | --- | --- | --- |
| Control-plane runtime | Yes | Read-only | No write path or change governance |
| Policy boundary outside the model | Yes | Deterministic | No real OPA execution |
| Typed capability surface | Yes | Mock rail | No real bank/rail integration |
| Split state and provenance | Yes | Projection scope limited | Not all provenance classes are projected asynchronously |
| Delegated-agent runtime | Yes | Narrow slice | No broader multi-agent task families or delegated credentials |
| MCP interoperability | Yes | Orchestrator-focused | No A2A / ACP / SLIM runtime |
| Durable workflow engine | No | Local worker only | No Temporal-native active path |
| Broker-backed messaging | No | Local outbox projection | No broader NATS/Kafka runtime |
| Security posture | Partial | Policy and provenance are strong for a PoC | No delegated tokens, anomaly scoring, mTLS, or strong IAM |
| Observability | Partial | Tests and service health exist | No production telemetry stack |
| Ops console | Yes | Early operator slice | No auth, server-side queueing, or deeper investigations yet |

\newpage

# 17. Conclusion

The repository has moved beyond architecture intent and now implements the core separation pattern in runnable form:

- `control-plane` publishes control and registry data
- `policy-engine` makes deterministic decisions outside the model
- `orchestrator-api` coordinates intake and resume through REST and MCP
- `workflow-worker` owns the active execution path
- `capability-gateway` isolates typed execution capabilities
- `context-memory-service` and `provenance-service` split current state from evidence
- `event-consumer` provides the first explicit consistency path between those boundaries
- `ops-console` gives operators a usable surface for creation, approval, review, and architecture-guided navigation

The architecture is therefore strongest today in:

- separation of concerns
- explicit workflow state
- provenance and delegation tracking
- policy outside the model
- operator-facing clarity

The architecture is still weakest in:

- control-plane governance
- production identity and delegated authorization
- real policy-engine execution against OPA bundles
- durable workflow runtime infrastructure
- production observability
- real bank and rail integration

That is the right shape for the current stage. The project has crossed the line from concept to constrained execution, and the remaining work is concentrated in production hardening rather than fundamental architectural direction.

\newpage

# Appendix A: Architecture Readiness Checklist

Use this checklist when evaluating whether the proof of concept is ready to expand in scope or authority.

| Checklist item | Current status | Notes |
| --- | --- | --- |
| Control, policy, workflow, state, and provenance are separate | Yes | Core architecture thesis is implemented |
| Release path is approval-gated | Yes | Approval resume required before release |
| Release behavior is idempotency-aware | Yes | Implemented in `capability-gateway` |
| Current state is durable and queryable | Yes | `context-memory-service` |
| Provenance is durable and queryable | Yes | `provenance-service` |
| Delegated work is explicit | Yes | Narrow runtime slice in place |
| Control publication has a runtime boundary | Yes | `control-plane`, read-only |
| Control changes are governed through versioned write paths | No | Still missing |
| Policy evaluation is deterministic and external to the model | Yes | `policy-engine` |
| Policy evaluation is true OPA-backed runtime decisioning | No | Still missing |
| Workflow runtime is durable under a workflow engine | No | Still missing |
| Messaging is broker-backed for the broader runtime | No | Still missing |
| Delegated credentials are signed and scope-enforced | No | Still missing |
| Production observability stack is present | No | Still missing |
| Real external rail integration exists | No | Still mock-based |
| Operator console exists | Yes | Early but usable |

Recommended go/no-go rule:

- do not expand execution authority beyond the current PoC slice until control-plane governance, stronger policy execution, delegated authorization, and durable workflow infrastructure are in place
