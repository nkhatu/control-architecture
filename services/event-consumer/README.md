# Event Consumer

This service handles asynchronous messages from the workflow and capability layers.

Initial subscriptions:

- `payments.events`
- `policy.decisions`
- `approvals.events`
- `reconciliation.events`

Initial responsibilities:

- project workflow events into a task read model
- update audit timelines
- detect stale or conflicting states
- trigger manual-review records when ambiguous downstream outcomes appear
