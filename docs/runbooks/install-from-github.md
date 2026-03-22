# Install From GitHub

This runbook starts from the public GitHub repository and walks through a clean local install of the control-architecture PoC.

Repository:

- [https://github.com/nkhatu/control-architecture](https://github.com/nkhatu/control-architecture)

This guide is organized for the fastest path first:

1. clone the repo
2. install local dependencies
3. run the backend stack with local SQLite
4. run the `ops-console`
5. verify the flow end to end

Use this runbook if you are starting from zero. If you already cloned the repo and installed the tools, use [local-setup.md](./local-setup.md) and [end-to-end-test.md](./end-to-end-test.md).

## 1. Install Required Tools

You need:

- `git`
- Python `3.12+`
- `uv`
- Node.js `20+`
- `npm`
- Docker Desktop or another local Docker runtime
- `make`

### macOS example with Homebrew

If you are on macOS and use Homebrew, this is the fastest install path:

```bash
brew install python@3.13 uv node make git
```

Install Docker Desktop separately and make sure it is running before you try any Docker-backed steps.

### Verify the tools

Run:

```bash
git --version
python3 --version
uv --version
node --version
npm --version
docker --version
make --version
```

Expected:

- Python is `3.12+`
- Node is `20+`
- each command returns a version instead of `command not found`

## 2. Clone the Repository

Run:

```bash
git clone https://github.com/nkhatu/control-architecture.git
cd control-architecture
```

If you want to work from a fork instead, clone your fork and keep the rest of this guide the same.

## 3. Review the Repo Shape

The main runtime boundaries are:

- `apps/control-plane`
- `apps/policy-engine`
- `apps/capability-gateway`
- `apps/orchestrator-api`
- `apps/ops-console`
- `services/context-memory-service`
- `services/provenance-service`
- `services/event-consumer`
- `services/workflow-worker`

The quickest backend path today is local Python services plus SQLite for the split state boundary.

## 4. Create Local Environment File

Copy the example file:

```bash
cp .env.example .env
```

Then review:

- [../../.env.example](../../.env.example)
- [../../config/control-plane/default.yaml](../../config/control-plane/default.yaml)

For the fastest local run, you can leave most values unchanged.

## 5. Install Backend Dependencies

From the repo root, run:

```bash
uv sync --extra dev
```

This creates the local Python environment and installs the backend dependencies used by the services and tests.

## 6. Install Frontend Dependencies

From the repo root, run:

```bash
npm --prefix apps/ops-console install
```

This installs the React/Vite dependencies for the operator console.

## 7. Choose a Runtime Path

There are two reasonable ways to run the repo locally.

### Option A: Fastest Local Path

Use SQLite for `context-memory-service` and `provenance-service`.

This path is best if you want to get the PoC running quickly and validate the control-architecture pattern end to end.

### Option B: Docker-Backed Infra

Bring up local infra services:

```bash
make infra-up
```

This starts:

- Postgres on `5432`
- Redis on `6379`
- NATS on `4222`
- OPA on `8181`
- Temporal on `7233`
- Temporal UI on `8080`

Current practical note:

- the repo has Docker scaffolding, but the fastest working application flow still uses local SQLite for the split state services
- Temporal/NATS/Postgres integration is still a partial area in the implementation table

If you are just installing from GitHub for the first time, start with **Option A**.

## 8. Start the Backend Stack

Open separate terminals from the repo root.

### Terminal 1: Context Memory

```bash
CONTEXT_MEMORY_AUTO_CREATE_SCHEMA=true \
CONTEXT_MEMORY_DATABASE_URL=sqlite+pysqlite:///./.tmp-context.db \
uv run uvicorn context_memory_service.main:app --reload --host 0.0.0.0 --port 8002
```

### Terminal 2: Provenance

```bash
PROVENANCE_AUTO_CREATE_SCHEMA=true \
PROVENANCE_DATABASE_URL=sqlite+pysqlite:///./.tmp-provenance.db \
uv run uvicorn provenance_service.main:app --reload --host 0.0.0.0 --port 8006
```

### Terminal 3: Event Consumer

```bash
uv run uvicorn event_consumer.main:app --reload --host 0.0.0.0 --port 8007
```

### Terminal 4: Control Plane

```bash
uv run uvicorn control_plane.main:app --reload --host 0.0.0.0 --port 8008
```

### Terminal 5: Policy Engine

```bash
uv run uvicorn policy_engine.main:app --reload --host 0.0.0.0 --port 8005
```

### Terminal 6: Capability Gateway

```bash
uv run uvicorn capability_gateway.main:app --reload --host 0.0.0.0 --port 8001
```

### Terminal 7: Workflow Worker

```bash
uv run uvicorn workflow_worker.main:app --reload --host 0.0.0.0 --port 8004
```

### Terminal 8: Orchestrator API

```bash
uv run uvicorn orchestrator_api.main:app --reload --host 0.0.0.0 --port 8000
```

## 9. Verify Backend Health

Open one more terminal and run:

```bash
curl http://127.0.0.1:8008/health
curl http://127.0.0.1:8005/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8004/health
curl http://127.0.0.1:8000/health
```

Expected:

- each endpoint returns `200 OK`
- the services report normally without connection failures

## 10. Start the Ops Console

From the repo root:

```bash
cd apps/ops-console
npm run dev -- --host 127.0.0.1 --port 3000
```

Then open:

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

The console currently includes:

- a blue theme
- a top-menu layout
- `Overview`
- `Create Payment`
- `Approvals`
- `Task Explorer`
- `Exceptions`

The frontend proxies:

- `/api/orchestrator` to `http://127.0.0.1:8000`
- `/api/control-plane` to `http://127.0.0.1:8008`

## 11. Run the Automated Test Suite

From the repo root:

```bash
uv run pytest
```

You can also build the frontend:

```bash
cd apps/ops-console
npm run build
```

## 12. Validate the First End-to-End Flow

For the full manual walkthrough, use:

- [end-to-end-test.md](./end-to-end-test.md)

That runbook covers:

- creating a domestic payment task
- waiting at approval
- resuming after approval
- confirming merged task state, artifacts, and delegations

## 13. Common Issues

### `uv: command not found`

Install it and retry:

```bash
brew install uv
```

### `npm error Missing script: "dev"`

You are probably not inside `apps/ops-console`.

Use:

```bash
cd apps/ops-console
npm run
```

You should see `dev`, `build`, and `preview`.

### Docker will not connect

Make sure Docker Desktop is fully running before you use:

```bash
make infra-up
docker ps
```

### Port already in use

Inspect the port:

```bash
lsof -i :3000
lsof -i :8000
```

Then stop the existing process or choose a different port.

### Frontend loads but APIs fail

Make sure these are running:

- `orchestrator-api` on `8000`
- `control-plane` on `8008`

## 14. Cleanup

Stop the Python services with `Ctrl+C` in each terminal.

If you used the local SQLite path, you can remove the temporary files:

```bash
rm -f .tmp-context.db .tmp-provenance.db
```

If you started Docker infra, shut it down with:

```bash
make infra-down
```
