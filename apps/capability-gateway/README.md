# Capability Gateway

This service exposes narrow, typed wrappers around domestic payment actions.

Initial PoC capabilities:

- create domestic payment instruction
- validate beneficiary account
- release approved payment
- check payment status
- cancel pending payment

PoC implementation notes:

- Start with a mock rail adapter instead of a bank integration.
- Emit explicit side-effect classes and idempotency behavior in responses.
- Never bury approval requirements inside service code or prompt text.
- Return structured error classes such as `policy_denied`, `duplicate_request`, and `state_conflict`.

## Bootstrap Status

This service now has a runnable FastAPI skeleton under [main.py](/Users/enkay/Documents/Scripts/Control%20Architecture/apps/capability-gateway/src/capability_gateway/main.py).

Current PoC slice:

- accepts domestic payment instruction requests and returns a typed task envelope
- validates beneficiaries through a deterministic mock rail adapter
- releases approved payments with explicit `success`, `reject`, and `ambiguous` mock outcomes
- tracks idempotency replay behavior for release requests
- exposes payment status lookups for the mock execution state

## Local Run

From the repo root:

```bash
uv sync --extra dev
uv run uvicorn capability_gateway.main:app --reload --host 0.0.0.0 --port 8001
```

## Local Test

```bash
uv run pytest
```
