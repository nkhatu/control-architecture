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
