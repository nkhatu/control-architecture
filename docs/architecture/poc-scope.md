# PoC Scope

## What the PoC should prove

- explicit task state is durable and queryable
- policy decisions stay outside the model
- release requires approved state plus idempotency key plus scoped authority
- ambiguous execution responses degrade to `pending_reconcile`
- end-to-end provenance survives orchestration, delegation, and execution

## In Scope

- domestic ACH, same-day ACH, and internal transfer only
- mock beneficiary validation
- mock approval workflow
- mock release through a capability gateway
- one durable release workflow in Temporal
- one policy bundle in OPA
- one async event bus using NATS
- one operator view for approvals and exceptions

## Out of Scope

- real bank connectivity
- international wires, FX, cards, or core ledger replacement
- sanctions policy authoring
- production SSO and production-grade secrets rotation
- SLIM transport implementation
- generalized multi-agent marketplace

## First Success Scenarios

1. Happy path: validated payment waits for approval, is approved, then releases and moves to `settlement_pending`.
2. Denied path: release is blocked because the payment is not approved or the caller lacks scope.
3. Safe failure path: mock rail returns an ambiguous response and the workflow moves to `pending_reconcile`.
