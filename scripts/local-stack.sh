#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_DIR="${REPO_ROOT}/.local-stack"
LOG_DIR="${RUNTIME_DIR}/logs"
PID_DIR="${RUNTIME_DIR}/pids"

DEFAULT_ENV_FILE="${REPO_ROOT}/.env"
FALLBACK_ENV_FILE="${REPO_ROOT}/.env.example"

SERVICE_NAMES=(
  "context-memory-service"
  "provenance-service"
  "event-consumer"
  "control-plane"
  "policy-engine"
  "capability-gateway"
  "workflow-worker"
  "orchestrator-api"
  "ops-console"
)

usage() {
  cat <<'EOF'
Usage:
  scripts/local-stack.sh up
  scripts/local-stack.sh down
  scripts/local-stack.sh status
  scripts/local-stack.sh logs <service-name>

Environment overrides:
  LOCAL_STACK_USE_SQLITE=true|false   Default: true
  LOCAL_STACK_INCLUDE_OPS_CONSOLE=true|false   Default: true
  LOCAL_STACK_ENV_FILE=/path/to/.env

The script:
  - starts Docker infra with `make infra-up`
  - starts the local backend services in the documented order
  - starts the ops console dev server by default
  - writes pid files and logs under `.local-stack/`

Examples:
  scripts/local-stack.sh up
  LOCAL_STACK_INCLUDE_OPS_CONSOLE=false scripts/local-stack.sh up
  scripts/local-stack.sh logs orchestrator-api
  scripts/local-stack.sh down
EOF
}

log() {
  printf '[local-stack] %s\n' "$*"
}

fail() {
  printf '[local-stack] ERROR: %s\n' "$*" >&2
  exit 1
}

ensure_command() {
  local command_name="$1"
  command -v "${command_name}" >/dev/null 2>&1 || fail "Missing required command: ${command_name}"
}

service_pid_file() {
  local service_name="$1"
  printf '%s/%s.pid' "${PID_DIR}" "${service_name}"
}

service_log_file() {
  local service_name="$1"
  printf '%s/%s.log' "${LOG_DIR}" "${service_name}"
}

service_health_url() {
  local service_name="$1"
  case "${service_name}" in
    "context-memory-service")
      printf 'http://127.0.0.1:%s/health' "${CONTEXT_MEMORY_SERVICE_PORT}"
      ;;
    "provenance-service")
      printf 'http://127.0.0.1:%s/health' "${PROVENANCE_SERVICE_PORT}"
      ;;
    "event-consumer")
      printf 'http://127.0.0.1:%s/health' "${EVENT_CONSUMER_PORT}"
      ;;
    "control-plane")
      printf 'http://127.0.0.1:%s/health' "${CONTROL_PLANE_PORT}"
      ;;
    "policy-engine")
      printf 'http://127.0.0.1:%s/health' "${POLICY_ENGINE_PORT}"
      ;;
    "capability-gateway")
      printf 'http://127.0.0.1:%s/health' "${CAPABILITY_GATEWAY_PORT}"
      ;;
    "workflow-worker")
      printf 'http://127.0.0.1:%s/health' "${WORKFLOW_WORKER_PORT}"
      ;;
    "orchestrator-api")
      printf 'http://127.0.0.1:%s/health' "${ORCHESTRATOR_API_PORT}"
      ;;
    "ops-console")
      printf 'http://127.0.0.1:%s' "${OPS_CONSOLE_PORT}"
      ;;
    *)
      return 1
      ;;
  esac
}

cleanup_stale_pid() {
  local service_name="$1"
  local pid_file
  pid_file="$(service_pid_file "${service_name}")"
  if [[ ! -f "${pid_file}" ]]; then
    return 0
  fi

  local pid
  pid="$(<"${pid_file}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    return 0
  fi

  rm -f "${pid_file}"
}

is_service_running() {
  local service_name="$1"
  cleanup_stale_pid "${service_name}"

  local pid_file
  pid_file="$(service_pid_file "${service_name}")"
  if [[ ! -f "${pid_file}" ]]; then
    return 1
  fi

  local pid
  pid="$(<"${pid_file}")"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

wait_for_http() {
  local service_name="$1"
  local health_url="$2"
  local attempts="${3:-60}"

  for ((i = 1; i <= attempts; i += 1)); do
    if curl -fsS "${health_url}" >/dev/null 2>&1; then
      log "${service_name} is healthy at ${health_url}"
      return 0
    fi
    sleep 1
  done

  fail "${service_name} did not become healthy. See $(service_log_file "${service_name}")"
}

start_shell_command() {
  local service_name="$1"
  local workdir="$2"
  local health_url="$3"
  local command="$4"

  cleanup_stale_pid "${service_name}"
  if is_service_running "${service_name}"; then
    log "${service_name} is already running"
    return 0
  fi

  local pid_file log_file
  pid_file="$(service_pid_file "${service_name}")"
  log_file="$(service_log_file "${service_name}")"

  log "Starting ${service_name}"
  (
    cd "${workdir}"
    nohup bash -lc "${command}" >"${log_file}" 2>&1 &
    echo $! >"${pid_file}"
  )

  wait_for_http "${service_name}" "${health_url}"
}

stop_service() {
  local service_name="$1"
  local pid_file
  pid_file="$(service_pid_file "${service_name}")"

  cleanup_stale_pid "${service_name}"
  if [[ ! -f "${pid_file}" ]]; then
    return 0
  fi

  local pid
  pid="$(<"${pid_file}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    log "Stopping ${service_name} (pid ${pid})"
    kill "${pid}" >/dev/null 2>&1 || true
    for _ in {1..20}; do
      if ! kill -0 "${pid}" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
  fi

  rm -f "${pid_file}"
}

load_environment() {
  local env_file="${LOCAL_STACK_ENV_FILE:-${DEFAULT_ENV_FILE}}"

  if [[ -f "${env_file}" ]]; then
    log "Loading environment from ${env_file}"
    set -a
    # shellcheck source=/dev/null
    source "${env_file}"
    set +a
  elif [[ -f "${FALLBACK_ENV_FILE}" ]]; then
    log "Loading environment defaults from ${FALLBACK_ENV_FILE}"
    set -a
    # shellcheck source=/dev/null
    source "${FALLBACK_ENV_FILE}"
    set +a
  fi

  export LOCAL_STACK_USE_SQLITE="${LOCAL_STACK_USE_SQLITE:-true}"
  export LOCAL_STACK_INCLUDE_OPS_CONSOLE="${LOCAL_STACK_INCLUDE_OPS_CONSOLE:-true}"

  export ORCHESTRATOR_API_PORT="${ORCHESTRATOR_API_PORT:-8000}"
  export CAPABILITY_GATEWAY_PORT="${CAPABILITY_GATEWAY_PORT:-8001}"
  export CONTEXT_MEMORY_SERVICE_PORT="${CONTEXT_MEMORY_SERVICE_PORT:-8002}"
  export WORKFLOW_WORKER_PORT="${WORKFLOW_WORKER_PORT:-8004}"
  export POLICY_ENGINE_PORT="${POLICY_ENGINE_PORT:-8005}"
  export PROVENANCE_SERVICE_PORT="${PROVENANCE_SERVICE_PORT:-8006}"
  export EVENT_CONSUMER_PORT="${EVENT_CONSUMER_PORT:-8007}"
  export CONTROL_PLANE_PORT="${CONTROL_PLANE_PORT:-8008}"
  export OPS_CONSOLE_PORT="${OPS_CONSOLE_PORT:-3000}"

  export CONTEXT_MEMORY_SERVICE_BASE_URL="${CONTEXT_MEMORY_SERVICE_BASE_URL:-http://localhost:${CONTEXT_MEMORY_SERVICE_PORT}}"
  export CAPABILITY_GATEWAY_BASE_URL="${CAPABILITY_GATEWAY_BASE_URL:-http://localhost:${CAPABILITY_GATEWAY_PORT}}"
  export WORKFLOW_WORKER_BASE_URL="${WORKFLOW_WORKER_BASE_URL:-http://localhost:${WORKFLOW_WORKER_PORT}}"
  export POLICY_ENGINE_BASE_URL="${POLICY_ENGINE_BASE_URL:-http://localhost:${POLICY_ENGINE_PORT}}"
  export PROVENANCE_SERVICE_BASE_URL="${PROVENANCE_SERVICE_BASE_URL:-http://localhost:${PROVENANCE_SERVICE_PORT}}"
  export EVENT_CONSUMER_BASE_URL="${EVENT_CONSUMER_BASE_URL:-http://localhost:${EVENT_CONSUMER_PORT}}"
  export CONTROL_PLANE_BASE_URL="${CONTROL_PLANE_BASE_URL:-http://localhost:${CONTROL_PLANE_PORT}}"

  if [[ "${LOCAL_STACK_USE_SQLITE}" == "true" ]]; then
    export CONTEXT_MEMORY_AUTO_CREATE_SCHEMA="true"
    export PROVENANCE_AUTO_CREATE_SCHEMA="true"
    export CONTEXT_MEMORY_DATABASE_URL="sqlite+pysqlite:///./.tmp-context.db"
    export PROVENANCE_DATABASE_URL="sqlite+pysqlite:///./.tmp-provenance.db"
  fi
}

ensure_runtime_dirs() {
  mkdir -p "${LOG_DIR}" "${PID_DIR}"
}

print_summary() {
  cat <<EOF

Local stack is running.

Core URLs:
  orchestrator-api:    http://127.0.0.1:${ORCHESTRATOR_API_PORT}
  capability-gateway:  http://127.0.0.1:${CAPABILITY_GATEWAY_PORT}
  control-plane:       http://127.0.0.1:${CONTROL_PLANE_PORT}
  policy-engine:       http://127.0.0.1:${POLICY_ENGINE_PORT}
  workflow-worker:     http://127.0.0.1:${WORKFLOW_WORKER_PORT}
  context-memory:      http://127.0.0.1:${CONTEXT_MEMORY_SERVICE_PORT}
  provenance:          http://127.0.0.1:${PROVENANCE_SERVICE_PORT}
  event-consumer:      http://127.0.0.1:${EVENT_CONSUMER_PORT}
  ops-console:         http://127.0.0.1:${OPS_CONSOLE_PORT}
  temporal-ui:         http://127.0.0.1:8080

Logs:
  ${LOG_DIR}

Use:
  scripts/local-stack.sh status
  scripts/local-stack.sh logs orchestrator-api
  scripts/local-stack.sh down
EOF
}

up() {
  ensure_command make
  ensure_command docker
  ensure_command curl
  ensure_command uv
  if [[ "${LOCAL_STACK_INCLUDE_OPS_CONSOLE}" == "true" ]]; then
    ensure_command npm
  fi

  log "Starting Docker infra"
  (
    cd "${REPO_ROOT}"
    make infra-up
  )

  start_shell_command \
    "context-memory-service" \
    "${REPO_ROOT}" \
    "$(service_health_url "context-memory-service")" \
    "uv run uvicorn context_memory_service.main:app --host 0.0.0.0 --port ${CONTEXT_MEMORY_SERVICE_PORT}"

  start_shell_command \
    "provenance-service" \
    "${REPO_ROOT}" \
    "$(service_health_url "provenance-service")" \
    "uv run uvicorn provenance_service.main:app --host 0.0.0.0 --port ${PROVENANCE_SERVICE_PORT}"

  start_shell_command \
    "event-consumer" \
    "${REPO_ROOT}" \
    "$(service_health_url "event-consumer")" \
    "uv run uvicorn event_consumer.main:app --host 0.0.0.0 --port ${EVENT_CONSUMER_PORT}"

  start_shell_command \
    "control-plane" \
    "${REPO_ROOT}" \
    "$(service_health_url "control-plane")" \
    "uv run uvicorn control_plane.main:app --host 0.0.0.0 --port ${CONTROL_PLANE_PORT}"

  start_shell_command \
    "policy-engine" \
    "${REPO_ROOT}" \
    "$(service_health_url "policy-engine")" \
    "uv run uvicorn policy_engine.main:app --host 0.0.0.0 --port ${POLICY_ENGINE_PORT}"

  start_shell_command \
    "capability-gateway" \
    "${REPO_ROOT}" \
    "$(service_health_url "capability-gateway")" \
    "uv run uvicorn capability_gateway.main:app --host 0.0.0.0 --port ${CAPABILITY_GATEWAY_PORT}"

  start_shell_command \
    "workflow-worker" \
    "${REPO_ROOT}" \
    "$(service_health_url "workflow-worker")" \
    "uv run uvicorn workflow_worker.main:app --host 0.0.0.0 --port ${WORKFLOW_WORKER_PORT}"

  start_shell_command \
    "orchestrator-api" \
    "${REPO_ROOT}" \
    "$(service_health_url "orchestrator-api")" \
    "uv run uvicorn orchestrator_api.main:app --host 0.0.0.0 --port ${ORCHESTRATOR_API_PORT}"

  if [[ "${LOCAL_STACK_INCLUDE_OPS_CONSOLE}" == "true" ]]; then
    start_shell_command \
      "ops-console" \
      "${REPO_ROOT}/apps/ops-console" \
      "$(service_health_url "ops-console")" \
      "OPS_CONSOLE_PORT=${OPS_CONSOLE_PORT} npm run dev -- --host 0.0.0.0 --port ${OPS_CONSOLE_PORT}"
  fi

  print_summary
}

down() {
  for ((i = ${#SERVICE_NAMES[@]} - 1; i >= 0; i -= 1)); do
    stop_service "${SERVICE_NAMES[i]}"
  done

  log "Stopping Docker infra"
  (
    cd "${REPO_ROOT}"
    make infra-down
  )
}

status() {
  local service_name health_url pid pid_file status

  printf 'Service status\n'
  printf '%-24s %-10s %-8s %s\n' "SERVICE" "PROCESS" "HEALTH" "DETAIL"

  for service_name in "${SERVICE_NAMES[@]}"; do
    cleanup_stale_pid "${service_name}"
    pid_file="$(service_pid_file "${service_name}")"
    if [[ -f "${pid_file}" ]]; then
      pid="$(<"${pid_file}")"
      status="running"
    else
      pid="-"
      status="stopped"
    fi

    health_url="$(service_health_url "${service_name}")"
    if curl -fsS "${health_url}" >/dev/null 2>&1; then
      printf '%-24s %-10s %-8s %s\n' "${service_name}" "${status}" "ok" "${health_url}"
    else
      printf '%-24s %-10s %-8s %s\n' "${service_name}" "${status}" "down" "${health_url}"
    fi
  done

  printf '\nDocker infra\n'
  if ! (
    cd "${REPO_ROOT}"
    docker compose ps 2>/dev/null
  ); then
    log "Docker infra status unavailable"
  fi
}

show_logs() {
  local service_name="${1:-}"
  [[ -n "${service_name}" ]] || fail "Usage: scripts/local-stack.sh logs <service-name>"

  local log_file
  log_file="$(service_log_file "${service_name}")"
  [[ -f "${log_file}" ]] || fail "No log file found for ${service_name}"
  tail -n 100 -f "${log_file}"
}

main() {
  local command="${1:-up}"
  case "${command}" in
    help|-h|--help)
      usage
      return 0
      ;;
    *)
      load_environment
      ensure_runtime_dirs
      ;;
  esac

  case "${command}" in
    up)
      up
      ;;
    down)
      down
      ;;
    status)
      status
      ;;
    logs)
      shift || true
      show_logs "${1:-}"
      ;;
    *)
      usage
      fail "Unknown command: ${command}"
      ;;
  esac
}

main "$@"
