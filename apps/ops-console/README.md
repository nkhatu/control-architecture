# Ops Console

The operator console is where deterministic human control stays visible.

Initial PoC screens:

- Approval queue for `awaiting_approval` tasks.
- Task explorer with current lifecycle state and provenance trail.
- Exception queue for `pending_reconcile` and `exception` cases.
- Audit detail for policy decisions, capability calls, and delegated identities.

Recommended stack for the PoC:

- Next.js or React app.
- Read-only by default.
- Field-level masking for account data.
- No direct release calls from the UI without policy-backed backend endpoints.
