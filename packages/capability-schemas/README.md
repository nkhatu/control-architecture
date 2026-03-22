# Capability Schemas

This package holds the language-neutral JSON Schema contracts shared across services.

Its job is to describe payload shape, not to provide Python runtime models.

Start with:

- common protocol envelope
- domestic payment instruction request
- beneficiary validation result
- approval request
- release request
- payment status response
- durable task-state record

Use this package when:

- a payload needs to be validated outside Python
- a contract should be published as a schema document
- the ops console, MCP/tooling layer, or an external integrator needs a machine-readable contract

Do not use this package for:

- Python-only runtime response models
- policy thresholds or approval matrices
- service-local command objects

Relationship to nearby packages:

- `capability-schemas/` is the schema-document layer
- `shared-contracts/` is the Python runtime contract layer
- `policy-models/` is the versioned policy-data layer

The orchestrator, capability gateway, workflow worker, and ops console should depend on these schemas instead of inventing incompatible external payload shapes.
