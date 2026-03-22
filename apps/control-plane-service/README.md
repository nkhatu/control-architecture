# Control-Plane Service

This service is the read-only runtime boundary for the PoC control plane.

Current PoC slice:

- loads the current control-plane document from `config/control-plane/default.yaml`
- loads the capability registry from `config/registry/capabilities.yaml`
- loads the agent registry from `config/registry/agents.yaml`
- publishes a combined snapshot for operators and other services to inspect
- publishes document digests so callers can detect version drift
- exposes a control summary for kill switch, thresholds, release controls, and rail scope

This first slice is intentionally read-only. The rest of the stack can adopt it incrementally while existing services continue loading local config.

The current endpoints are:

- `GET /health`
- `GET /metadata`
- `GET /control-plane`
- `GET /controls/summary`
- `GET /registries/capabilities`
- `GET /registries/agents`
- `GET /versions/current`
- `GET /snapshot`

## Local Run

From the repo root:

```bash
uv sync --extra dev
uv run uvicorn control_plane_service.main:app --reload --host 0.0.0.0 --port 8008
```

## Local Test

```bash
uv run pytest apps/control-plane-service/tests/test_control_plane_service.py
```
