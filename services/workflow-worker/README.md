# Workflow Worker

This service owns durable workflow execution.

Use Temporal for:

- payment intake workflow
- validation workflow steps
- approval wait states
- release orchestration
- ambiguous response handling
- reconciliation handoff

The first workflow should model these states:

- `received`
- `validated`
- `awaiting_approval`
- `approved`
- `released`
- `settlement_pending`
- `pending_reconcile`
- `failed`
- `cancelled`
