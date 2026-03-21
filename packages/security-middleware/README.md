# Security Middleware

This package should hold reusable enforcement code that is shared by every service boundary.

Initial responsibilities:

- validate task-scoped delegated tokens
- stamp provenance metadata onto outbound calls
- require idempotency keys for release-adjacent actions
- redact PII in logs and events
- reject scope widening across delegation hops
