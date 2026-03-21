# Capability Schemas

This package holds the machine-readable contracts shared across services.

Start with:

- common protocol envelope
- domestic payment instruction request
- beneficiary validation result
- approval request
- release request
- payment status response
- durable task-state record

These schemas are the contract source of truth for the PoC. The orchestrator, capability gateway, workflow worker, and ops console should all depend on them instead of inventing local shapes.
