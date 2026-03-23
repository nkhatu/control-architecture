# Scripts

## `local-stack.sh`

Starts and stops the local PoC stack from one place.

Usage:

```bash
scripts/local-stack.sh up
scripts/local-stack.sh status
scripts/local-stack.sh logs orchestrator-api
scripts/local-stack.sh down
```

Default behavior:

- runs `make infra-up`
- starts the backend services in the documented order
- starts the `ops-console` dev server
- uses local SQLite files for `context-memory-service` and `provenance-service`
- writes logs and pid files under `.local-stack/`

Useful overrides:

```bash
LOCAL_STACK_INCLUDE_OPS_CONSOLE=false scripts/local-stack.sh up
LOCAL_STACK_USE_SQLITE=false scripts/local-stack.sh up
LOCAL_STACK_ENV_FILE=.env scripts/local-stack.sh up
```
