# PoC Threat Model

## High-Risk Failure Modes

- scope widening across delegation hops
- payment release without current approval state
- duplicate release attempts after retries or transport redelivery
- state confusion between draft, approved, released, and settled
- missing provenance for policy or execution decisions
- prompt or payload injection causing unauthorized tool invocation

## PoC Countermeasures

- task-scoped delegated tokens with short TTLs
- policy checks before every irreversible action
- idempotency required for `release_approved_payment`
- explicit workflow status model in durable storage
- immutable event IDs and correlation IDs on every message
- safe degrade to `pending_reconcile` for ambiguous downstream outcomes

## Open Gaps For Later Phases

- anomaly scoring
- real SSO integration
- mTLS between internal services
- production KMS or Vault integration
- adversarial test harness for tool misuse and malicious inputs
