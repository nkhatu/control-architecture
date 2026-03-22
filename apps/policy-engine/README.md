# Policy Engine

The PoC should keep policy deterministic and outside the model.

This app is the deterministic decision boundary the orchestrator calls before material actions.

Current PoC slice:

- domestic payment intake
- payment release
- normalized decisions: `allow`, `deny`, `escalate`, `simulate`
- control-plane thresholds loaded from `control-plane`, with local YAML fallback for isolated runs
- an OPA-aligned request shape for payment state, principal scopes, and request context

The current endpoints are:

- `POST /decisions/intake`
- `POST /decisions/release`
- `GET /health`
- `GET /metadata`

The PoC still keeps the Rego bundle in this directory as the policy reference, but the running service currently evaluates the same decisions in Python so the rest of the stack can integrate against a real policy boundary now.

## Local Run

From the repo root:

```bash
uv sync --extra dev
uv run uvicorn policy_engine.main:app --reload --host 0.0.0.0 --port 8005
```

## Local Test

```bash
uv run pytest
```
