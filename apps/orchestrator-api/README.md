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

## Bootstrap Status

This service now has a runnable FastAPI skeleton under [main.py](/Users/enkay/Documents/Scripts/Control%20Architecture/apps/orchestrator-api/src/orchestrator_api/main.py).

Current PoC slice:

- loads control-plane, capability, and agent registry YAML
- calls `policy-service` for deterministic intake and release decisions
- starts and resumes the domestic payment workflow through `workflow-worker`
- passes delegated-agent context into the workflow for compliance screening and approval routing
- persists and reads durable task state through `memory-service`
- writes `release_policy_decision` artifacts before release resumes
- exposes `GET /tasks/{task_id}` and `POST /tasks/{task_id}/resume`
- exposes an MCP server adapter with tools, resources, and a review prompt

## Local Run

From the repo root:

```bash
uv sync --extra dev
uv run uvicorn orchestrator_api.main:app --reload --host 0.0.0.0 --port 8000
```

Run the MCP server over stdio:

```bash
uv run python -m orchestrator_api.mcp_server
```

Run the MCP server over Streamable HTTP on `http://127.0.0.1:8003/mcp`:

```bash
ORCHESTRATOR_MCP_TRANSPORT=streamable-http uv run python -m orchestrator_api.mcp_server
```

## Local Test

```bash
uv run pytest
```
