# Ops Console

The ops console is the operator-facing UI for approvals, task review, and exception handling.

Current PoC slice:

- uses a top menu to move between overview, trust-graph navigation, payment intake, approvals, task explorer, and exception review
- reads control summary and snapshot metadata from `control-plane`
- creates domestic payment tasks through `orchestrator-api`
- keeps a local recent-task queue in the browser until a server-side queue endpoint exists
- includes a trust-graph page that uses the architecture image as a navigation surface into the console
- lets an operator load a task by id and inspect:
  - current lifecycle state
  - provenance summary
  - state history
  - artifacts
  - delegated work records
- lets an operator approve and resume an `awaiting_approval` task through `orchestrator-api`
- highlights exception-oriented tasks such as `pending_reconcile` and `exception`

The first console intentionally stays narrow and backend-aligned. It does not bypass policy or workflow controls, and it does not call release rails directly.

## Local Run

From the repo root:

```bash
cd apps/ops-console
npm install
npm run dev
```

The Vite dev server proxies API requests to:

- `http://127.0.0.1:8000` for `orchestrator-api`
- `http://127.0.0.1:8008` for `control-plane`

Set `OPS_CONSOLE_PORT` if you want a port other than `3000`.

## Local Build

```bash
cd apps/ops-console
npm run build
```
