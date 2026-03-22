# Shared Contracts

This package holds the typed Python contracts that backend services share at runtime.

Current contents:

- task lifecycle outbox event models
- task context, provenance, and merged task-detail view models
- helpers for merging context and provenance into a single read model

Use this package when:

- a Python service needs to import and return the same typed model as another Python service
- an internal HTTP client should validate a response into a shared runtime contract
- the outbox or projection path needs a canonical typed event payload

Do not use this package for:

- JSON Schema documents intended to be language-neutral
- policy thresholds or approval matrices
- service-local command models that are only meaningful inside one bounded context

Relationship to nearby packages:

- `shared-contracts/` is the Python runtime contract layer.
- `capability-schemas/` is the language-neutral schema layer.
- `policy-models/` is the versioned policy-data layer.

Current examples in this repo live under:

- [tasks.py](/Users/enkay/Documents/Scripts/Control%20Architecture/packages/shared-contracts/src/shared_contracts/tasks.py)
- [events.py](/Users/enkay/Documents/Scripts/Control%20Architecture/packages/shared-contracts/src/shared_contracts/events.py)
