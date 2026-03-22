# Policy Models

Keep versioned policy data here rather than hard-coding it in services.

This package is for policy configuration and policy fixtures, not for request/response schema definitions and not for the runtime evaluation service itself.

Expected artifacts:

- approval matrices
- amount thresholds
- rail restrictions
- beneficiary restriction lists
- role-to-scope maps
- test fixtures for allow, deny, and escalate outcomes

Use this package when:

- the policy-engine needs versioned thresholds or approval metadata
- a control-plane rule should be represented as data instead of code
- tests need stable policy fixtures

Do not use this package for:

- Python runtime DTOs shared between services
- JSON Schema contract documents
- the policy-engine API handlers or decision engine itself

Relationship to nearby packages:

- `policy-models/` is the policy-data layer
- `shared-contracts/` is the Python runtime contract layer
- `capability-schemas/` is the schema-document layer
