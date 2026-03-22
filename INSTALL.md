# Install

Use this file as the entry point for setting up the control-architecture PoC from GitHub.

The full step-by-step install guide is here:

- [docs/runbooks/install-from-github.md](docs/runbooks/install-from-github.md)

## Quick Start

1. Clone the repository:

```bash
git clone https://github.com/nkhatu/control-architecture.git
cd control-architecture
```

2. Copy the local environment file:

```bash
cp .env.example .env
```

3. Install backend dependencies:

```bash
uv sync --extra dev
```

4. Install frontend dependencies:

```bash
npm --prefix apps/ops-console install
```

5. Start the backend stack using the local SQLite path:

```bash
CONTEXT_MEMORY_AUTO_CREATE_SCHEMA=true \
CONTEXT_MEMORY_DATABASE_URL=sqlite+pysqlite:///./.tmp-context.db \
uv run uvicorn context_memory_service.main:app --reload --host 0.0.0.0 --port 8002
```

```bash
PROVENANCE_AUTO_CREATE_SCHEMA=true \
PROVENANCE_DATABASE_URL=sqlite+pysqlite:///./.tmp-provenance.db \
uv run uvicorn provenance_service.main:app --reload --host 0.0.0.0 --port 8006
```

```bash
uv run uvicorn event_consumer.main:app --reload --host 0.0.0.0 --port 8007
```

```bash
uv run uvicorn control_plane.main:app --reload --host 0.0.0.0 --port 8008
```

```bash
uv run uvicorn policy_engine.main:app --reload --host 0.0.0.0 --port 8005
```

```bash
uv run uvicorn capability_gateway.main:app --reload --host 0.0.0.0 --port 8001
```

```bash
uv run uvicorn workflow_worker.main:app --reload --host 0.0.0.0 --port 8004
```

```bash
uv run uvicorn orchestrator_api.main:app --reload --host 0.0.0.0 --port 8000
```

6. Start the operator console:

```bash
cd apps/ops-console
npm run dev -- --host 127.0.0.1 --port 3000
```

7. Open the console:

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

## Next Docs

- Full install guide: [docs/runbooks/install-from-github.md](docs/runbooks/install-from-github.md)
- Local setup: [docs/runbooks/local-setup.md](docs/runbooks/local-setup.md)
- Manual end-to-end verification: [docs/runbooks/end-to-end-test.md](docs/runbooks/end-to-end-test.md)
