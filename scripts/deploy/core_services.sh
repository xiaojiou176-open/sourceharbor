#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/compose/core-services.compose.yml"
ENV_FILE="$ROOT_DIR/.env"
RUN_DIR="$ROOT_DIR/.runtime-cache/run/local-core"
LOG_DIR="$ROOT_DIR/.runtime-cache/logs/local-core"
POSTGRES_DATA_DIR="$ROOT_DIR/.runtime-cache/tmp/local-postgres/data"
POSTGRES_PID_FILE="$RUN_DIR/postgres.pid"
TEMPORAL_PID_FILE="$RUN_DIR/temporal.pid"
POSTGRES_LOG_PATH="$LOG_DIR/postgres.log"
TEMPORAL_LOG_PATH="$LOG_DIR/temporal.log"
CORE_POSTGRES_PORT_DEFAULT="15432"
TEMPORAL_PORT_DEFAULT="7233"

# shellcheck source=scripts/lib/load_env.sh
source "$ROOT_DIR/scripts/lib/load_env.sh"

eval "$(python3 "$ROOT_DIR/scripts/ci/contract.py" shell-exports)"

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy/core_services.sh [up|down|restart|status|logs] [--env-file <path>]

SourceHarbor local core services compose helper.
Starts or inspects the repo-local Postgres + Temporal stack from
infra/compose/core-services.compose.yml.
When Docker Desktop is unavailable but the local machine has `postgres`/`pg_ctl`
and `temporal` binaries, this helper can fall back to repo-owned local core
services under `.runtime-cache/`.
This is not a product distribution image installer or hosted runtime surface.
EOF
}

command="up"
while [[ $# -gt 0 ]]; do
  case "$1" in
    up|down|restart|status|logs) command="$1"; shift ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

CORE_POSTGRES_PORT="${CORE_POSTGRES_PORT:-$CORE_POSTGRES_PORT_DEFAULT}"
TEMPORAL_TARGET_HOST="${TEMPORAL_TARGET_HOST:-127.0.0.1:${TEMPORAL_PORT_DEFAULT}}"
TEMPORAL_PORT="${TEMPORAL_TARGET_HOST##*:}"

mkdir -p "$RUN_DIR" "$LOG_DIR" "$ROOT_DIR/.runtime-cache/tmp/local-postgres"

docker_compose_available() {
  command -v docker >/dev/null 2>&1 || return 1
  docker compose version >/dev/null 2>&1 || return 1
  timeout 5 docker ps >/dev/null 2>&1
}

local_core_binaries_available() {
  command -v postgres >/dev/null 2>&1 \
    && command -v initdb >/dev/null 2>&1 \
    && command -v pg_ctl >/dev/null 2>&1 \
    && command -v temporal >/dev/null 2>&1
}

port_listening() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    return $?
  fi
  return 1
}

cleanup_stale_pid_file() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
  fi
}

spawn_temporal_local_fallback() {
  TEMPORAL_LOG_PATH="$TEMPORAL_LOG_PATH" \
  TEMPORAL_IP="127.0.0.1" \
  TEMPORAL_PORT="$TEMPORAL_PORT" \
    python3 - <<'PY'
import os
import subprocess
import sys

log_path = os.environ["TEMPORAL_LOG_PATH"]
host = os.environ["TEMPORAL_IP"]
port = os.environ["TEMPORAL_PORT"]

with open(log_path, "ab", buffering=0) as log_file:
    process = subprocess.Popen(
        [
            "temporal",
            "server",
            "start-dev",
            "--headless",
            "--ip",
            host,
            "--port",
            port,
        ],
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )

print(process.pid)
PY
}

wait_for_port() {
  local port="$1"
  local timeout_seconds="${2:-20}"
  local second
  for second in $(seq 1 "$timeout_seconds"); do
    if port_listening "$port"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

local_core_status() {
  cleanup_stale_pid_file "$POSTGRES_PID_FILE"
  cleanup_stale_pid_file "$TEMPORAL_PID_FILE"

  if [[ -f "$POSTGRES_PID_FILE" ]] && kill -0 "$(cat "$POSTGRES_PID_FILE")" 2>/dev/null; then
    echo "postgres: running (owned) pid=$(cat "$POSTGRES_PID_FILE") port=$CORE_POSTGRES_PORT"
  elif port_listening "$CORE_POSTGRES_PORT"; then
    echo "postgres: running (reused) port=$CORE_POSTGRES_PORT"
  else
    echo "postgres: stopped"
  fi

  if [[ -f "$TEMPORAL_PID_FILE" ]] && kill -0 "$(cat "$TEMPORAL_PID_FILE")" 2>/dev/null; then
    echo "temporal: running (owned) pid=$(cat "$TEMPORAL_PID_FILE") port=$TEMPORAL_PORT"
  elif port_listening "$TEMPORAL_PORT"; then
    echo "temporal: running (reused) port=$TEMPORAL_PORT"
  else
    echo "temporal: stopped"
  fi
}

local_core_up() {
  local abs_data_dir abs_log_path
  abs_data_dir="$(python3 - <<'PY' "$POSTGRES_DATA_DIR"
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"
  abs_log_path="$(python3 - <<'PY' "$POSTGRES_LOG_PATH"
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"

  if [[ ! -f "$POSTGRES_DATA_DIR/PG_VERSION" ]]; then
    initdb -D "$abs_data_dir" -U postgres -A trust >/dev/null
  fi

  if ! port_listening "$CORE_POSTGRES_PORT"; then
    pg_ctl -D "$abs_data_dir" -l "$abs_log_path" -o "-p ${CORE_POSTGRES_PORT} -h 127.0.0.1" start >/dev/null
    if pgrep -af "postgres.*-p ${CORE_POSTGRES_PORT}" >/dev/null 2>&1; then
      pgrep -af "postgres.*-p ${CORE_POSTGRES_PORT}" | head -n 1 | awk '{print $1}' > "$POSTGRES_PID_FILE"
    fi
  fi
  wait_for_port "$CORE_POSTGRES_PORT" 20 || {
    echo "[core-services] postgres failed to become reachable on port $CORE_POSTGRES_PORT" >&2
    exit 1
  }

  cleanup_stale_pid_file "$TEMPORAL_PID_FILE"
  if ! port_listening "$TEMPORAL_PORT"; then
    # Launch Temporal in its own session so the local fallback survives
    # bootstrap/full-stack parent shell exit instead of becoming a stale pid file.
    spawn_temporal_local_fallback > "$TEMPORAL_PID_FILE"
  fi
  wait_for_port "$TEMPORAL_PORT" 20 || {
    echo "[core-services] temporal failed to become reachable on port $TEMPORAL_PORT" >&2
    exit 1
  }

  echo "[core-services] local fallback active"
  local_core_status
}

local_core_down() {
  cleanup_stale_pid_file "$TEMPORAL_PID_FILE"
  cleanup_stale_pid_file "$POSTGRES_PID_FILE"

  if [[ -f "$TEMPORAL_PID_FILE" ]] && kill -0 "$(cat "$TEMPORAL_PID_FILE")" 2>/dev/null; then
    kill "$(cat "$TEMPORAL_PID_FILE")" 2>/dev/null || true
    rm -f "$TEMPORAL_PID_FILE"
  else
    rm -f "$TEMPORAL_PID_FILE"
  fi
  if [[ -f "$POSTGRES_PID_FILE" ]] && kill -0 "$(cat "$POSTGRES_PID_FILE")" 2>/dev/null; then
    pg_ctl -D "$POSTGRES_DATA_DIR" stop -m fast >/dev/null 2>&1 || kill "$(cat "$POSTGRES_PID_FILE")" 2>/dev/null || true
    rm -f "$POSTGRES_PID_FILE"
  else
    rm -f "$POSTGRES_PID_FILE"
  fi
}

local_core_logs() {
  tail -n 200 -f "$POSTGRES_LOG_PATH" "$TEMPORAL_LOG_PATH"
}

if docker_compose_available; then
  case "$command" in
    up) docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d ;;
    down) docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down ;;
    restart)
      docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down
      docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
      ;;
    status) docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps ;;
    logs) docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs -f --tail=200 ;;
  esac
  exit 0
fi

local_core_binaries_available || {
  echo "docker daemon unavailable and local postgres/temporal binaries not available" >&2
  exit 1
}

case "$command" in
  up) local_core_up ;;
  down) local_core_down ;;
  restart)
    local_core_down
    local_core_up
    ;;
  status) local_core_status ;;
  logs) local_core_logs ;;
esac
