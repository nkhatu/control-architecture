# Orchestrator API

This service is the intake and coordination boundary for the PoC.

Primary responsibilities:

- Accept domestic payment tasks.
- Load task context from the memory service.
- Resolve capability and agent registry entries.
- Request policy decisions before material actions.
- Start or resume Temporal workflows.
- Publish protocol envelopes for delegated work and workflow updates.

Suggested first endpoints:

- `POST /tasks/domestic-payments`
- `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/resume`
- `POST /protocol/messages`

Critical rule:

- The orchestrator decides the next step.
- The orchestrator does not make final release policy decisions.
