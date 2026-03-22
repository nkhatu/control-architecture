# Packages

`packages/` holds reusable assets that are shared across multiple services but are not deployable services themselves.

Use these packages with the following rule of thumb:

- `shared-contracts/`
  Use for Python runtime models that backend services import directly. These are typed Pydantic contracts used in process and across internal HTTP boundaries.
- `capability-schemas/`
  Use for language-neutral JSON Schema definitions. These are the machine-readable contract documents for protocol messages, capability requests, and shared payload validation.
- `policy-models/`
  Use for versioned policy data. This is where thresholds, approval matrices, scope maps, and policy fixtures should live.
- `security-middleware/`
  Use for reusable enforcement helpers shared across service boundaries.
- `observability/`
  Use for shared trace, metric, and structured logging conventions.

What does not belong here:

- service-specific request handlers
- database repositories
- workflow orchestration logic
- one-off payload shapes used by a single service only

Separation guidance:

- If the contract is a Python-native internal model used directly by backend code, put it in `shared-contracts/`.
- If the contract needs to be validated across languages, published externally, or treated as a schema document, put it in `capability-schemas/`.
- If the content controls policy behavior rather than message shape, put it in `policy-models/`.
