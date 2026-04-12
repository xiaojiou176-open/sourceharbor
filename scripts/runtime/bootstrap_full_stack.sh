#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="bootstrap_full_stack"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck source=./scripts/runtime/logging.sh
source "$ROOT_DIR/scripts/runtime/logging.sh"
sourceharbor_log_init "components" "$SCRIPT_NAME" "$ROOT_DIR/.runtime-cache/logs/components/full-stack/bootstrap-full-stack.jsonl"

# shellcheck source=./scripts/lib/load_env.sh
source "$ROOT_DIR/scripts/lib/load_env.sh"
# shellcheck source=./scripts/lib/standard_env.sh
source "$ROOT_DIR/scripts/lib/standard_env.sh"

PROFILE="local"
INSTALL_DEPS="1"
WITH_CORE_SERVICES="1"
WITH_READER_STACK="0"
READER_ENV_TEMPLATE_FILE="$ROOT_DIR/env/profiles/reader.env"
READER_ENV_LOCAL_FILE="$ROOT_DIR/env/profiles/reader.local.env"
if [[ -f "$READER_ENV_LOCAL_FILE" ]]; then
  READER_ENV_FILE="$READER_ENV_LOCAL_FILE"
else
  READER_ENV_FILE="$READER_ENV_TEMPLATE_FILE"
fi
API_PORT="9000"
WEB_PORT="3000"
API_PORT_EXPLICIT="0"
WEB_PORT_EXPLICIT="0"
RESOLVED_ENV_PATH="$(get_runtime_resolved_env_path "$ROOT_DIR")"
WORKSPACE_HYGIENE="$ROOT_DIR/scripts/runtime/workspace_hygiene.sh"

log() { sourceharbor_log info bootstrap "$*"; }
fail() { sourceharbor_log error bootstrap_error "$*"; exit 1; }

is_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

apply_psql_migrations() {
  local psql_url="$1"
  local migration
  local migration_name
  local migration_applied
  psql "$psql_url" -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
CREATE TABLE IF NOT EXISTS sourceharbor_schema_migrations (
  migration_name TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL
  for migration in $(cd "$ROOT_DIR" && ls infra/migrations/*.sql | sort); do
    migration_name="$(basename "$migration")"
    migration_applied="$(
      psql "$psql_url" -Atq <<SQL
SELECT 1
FROM sourceharbor_schema_migrations
WHERE migration_name = '${migration_name}'
LIMIT 1;
SQL
    )"
    if [[ "$migration_applied" == "1" ]]; then
      continue
    fi
    psql "$psql_url" -v ON_ERROR_STOP=1 <<SQL >/dev/null
BEGIN;
\i '$ROOT_DIR/$migration'
INSERT INTO sourceharbor_schema_migrations (migration_name)
VALUES ('${migration_name}');
COMMIT;
SQL
  done
}

port_in_use() {
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

pick_free_port() {
  local preferred="$1"
  shift
  local candidate
  if ! port_in_use "$preferred"; then
    echo "$preferred"
    return 0
  fi
  for candidate in "$@"; do
    if ! port_in_use "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  fail "no free port found from candidates: $preferred $*"
}

normalize_runtime_database_url() {
  local raw_url="${1:-}"
  local target_port="${2:-15432}"
  local default_password="${3:-postgres}"
  DATABASE_URL_TO_NORMALIZE="$raw_url" \
  TARGET_DATABASE_PORT="$target_port" \
  TARGET_DATABASE_PASSWORD="$default_password" \
    python3 - <<'PY'
from urllib.parse import urlsplit, urlunsplit
import os

raw = (os.environ.get("DATABASE_URL_TO_NORMALIZE") or "").strip()
target_port = (os.environ.get("TARGET_DATABASE_PORT") or "15432").strip()
default_password = os.environ.get("TARGET_DATABASE_PASSWORD", "postgres")

if not raw:
    raw = f"postgresql+psycopg://postgres:{default_password}@127.0.0.1:{target_port}/sourceharbor"

if raw.startswith("postgresql://"):
    raw = "postgresql+psycopg://" + raw[len("postgresql://"):]

parsed = urlsplit(raw)
scheme = parsed.scheme or "postgresql+psycopg"
if scheme == "postgresql":
    scheme = "postgresql+psycopg"

hostname = parsed.hostname or "127.0.0.1"
database_name = parsed.path.lstrip("/") or "sourceharbor"

if hostname in {"localhost", "127.0.0.1"}:
    username = parsed.username or "postgres"
    password = parsed.password or default_password
    netloc = f"{username}:{password}@127.0.0.1:{target_port}"
    print(urlunsplit((scheme, netloc, f"/{database_name}", parsed.query, parsed.fragment)))
else:
    print(urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment)))
PY
}

normalize_temporal_task_queue() {
  local raw_value="${1:-}"
  if [[ -z "$raw_value" || "$raw_value" == "sourceharbor" ]]; then
    printf 'sourceharbor-worker\n'
    return 0
  fi
  printf '%s\n' "$raw_value"
}

usage() {
  cat <<'EOF'
Usage: ./bin/bootstrap-full-stack [--profile local|gce] [--api-port <port>] [--web-port <port>] [--install-deps 0|1] [--with-core-services 0|1] [--with-reader-stack 0|1] [--reader-env-file <path>]

Goal:
  Clone repo and reach runnable state for 80%+ functionality.

Examples:
  ./bin/bootstrap-full-stack
  ./bin/bootstrap-full-stack --profile gce --with-reader-stack 1 --reader-env-file env/profiles/reader.local.env

Notes:
  - core services can use Docker compose or a repo-owned local fallback when Docker is unavailable
  - reader stack stays an explicit Docker-only optional lane
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --api-port) API_PORT="$2"; API_PORT_EXPLICIT="1"; shift 2 ;;
    --web-port) WEB_PORT="$2"; WEB_PORT_EXPLICIT="1"; shift 2 ;;
    --install-deps) INSTALL_DEPS="$2"; shift 2 ;;
    --with-core-services) WITH_CORE_SERVICES="$2"; shift 2 ;;
    --with-reader-stack) WITH_READER_STACK="$2"; shift 2 ;;
    --reader-env-file) READER_ENV_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ "$PROFILE" == "local" || "$PROFILE" == "gce" ]] || fail "--profile must be local|gce"
rm -f "$RESOLVED_ENV_PATH"

log "Normalizing forbidden workspace runtime residue"
bash "$WORKSPACE_HYGIENE" --apply >/dev/null || fail "workspace hygiene failed"

command -v python3 >/dev/null 2>&1 || fail "python3 not found"
command -v uv >/dev/null 2>&1 || fail "uv not found"
command -v npm >/dev/null 2>&1 || fail "npm not found"

if is_truthy "$INSTALL_DEPS"; then
  ensure_external_uv_project_environment "$ROOT_DIR"
  export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
  log "Installing Python deps via uv"
  (cd "$ROOT_DIR" && uv sync --frozen --extra dev --extra e2e)
  log "Preparing runtime web workspace"
  (cd "$ROOT_DIR" && bash scripts/ci/prepare_web_runtime.sh >/dev/null)
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  log "No .env found, creating from .env.example"
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

load_repo_env "$ROOT_DIR" "$SCRIPT_NAME" "$PROFILE"

api_port_cli=""
web_port_cli=""
if [[ "$API_PORT_EXPLICIT" == "1" ]]; then
  api_port_cli="$API_PORT"
fi
if [[ "$WEB_PORT_EXPLICIT" == "1" ]]; then
  web_port_cli="$WEB_PORT"
fi

API_PORT="$(resolve_runtime_route_value "$ROOT_DIR" "API_PORT" "$api_port_cli" "9000")"
WEB_PORT="$(resolve_runtime_route_value "$ROOT_DIR" "WEB_PORT" "$web_port_cli" "3000")"
CORE_POSTGRES_PORT="${CORE_POSTGRES_PORT:-15432}"
export CORE_POSTGRES_PORT
DATABASE_URL="$(resolve_runtime_route_value "$ROOT_DIR" "DATABASE_URL" "" "postgresql+psycopg://postgres:postgres@127.0.0.1:${CORE_POSTGRES_PORT}/sourceharbor")"
DATABASE_URL="$(normalize_runtime_database_url "$DATABASE_URL" "$CORE_POSTGRES_PORT" "${CORE_POSTGRES_PASSWORD:-postgres}")"
TEMPORAL_TARGET_HOST="$(resolve_runtime_route_value "$ROOT_DIR" "TEMPORAL_TARGET_HOST" "" "127.0.0.1:7233")"
TEMPORAL_NAMESPACE="$(resolve_runtime_route_value "$ROOT_DIR" "TEMPORAL_NAMESPACE" "" "default")"
TEMPORAL_TASK_QUEUE="$(resolve_runtime_route_value "$ROOT_DIR" "TEMPORAL_TASK_QUEUE" "" "sourceharbor-worker")"
TEMPORAL_TASK_QUEUE="$(normalize_temporal_task_queue "$TEMPORAL_TASK_QUEUE")"
export DATABASE_URL TEMPORAL_TARGET_HOST TEMPORAL_NAMESPACE TEMPORAL_TASK_QUEUE

if ! [[ "$API_PORT" =~ ^[0-9]+$ ]] || (( API_PORT <= 0 || API_PORT > 65535 )); then
  fail "--api-port must be an integer in [1,65535]"
fi
if ! [[ "$WEB_PORT" =~ ^[0-9]+$ ]] || (( WEB_PORT <= 0 || WEB_PORT > 65535 )); then
  fail "--web-port must be an integer in [1,65535]"
fi

API_PORT_CURRENT="$API_PORT"
WEB_PORT_CURRENT="$WEB_PORT"
API_PORT_PICKED="$(pick_free_port "$API_PORT_CURRENT" 18000 18001 18002)"
WEB_PORT_PICKED="$(pick_free_port "$WEB_PORT_CURRENT" 13000 13001 13002)"
if is_truthy "$WITH_READER_STACK"; then
  NEXTFLUX_PORT_CURRENT="${NEXTFLUX_PORT:-3000}"
  if [[ "$WEB_PORT_PICKED" == "$NEXTFLUX_PORT_CURRENT" ]]; then
    WEB_PORT_PICKED="$(pick_free_port 3001 13000 13001 13002)"
  fi
fi
if [[ "$API_PORT_PICKED" != "$API_PORT_CURRENT" || "$WEB_PORT_PICKED" != "$WEB_PORT_CURRENT" ]]; then
  log "Port conflict detected; using runtime API_PORT=${API_PORT_PICKED}, WEB_PORT=${WEB_PORT_PICKED}"
fi
API_PORT="$API_PORT_PICKED"
WEB_PORT="$WEB_PORT_PICKED"
SOURCE_HARBOR_API_BASE_URL="http://127.0.0.1:${API_PORT}"
NEXT_PUBLIC_API_BASE_URL="$SOURCE_HARBOR_API_BASE_URL"
export API_PORT WEB_PORT SOURCE_HARBOR_API_BASE_URL NEXT_PUBLIC_API_BASE_URL

log "Validating env contract"
(cd "$ROOT_DIR" && python3 scripts/governance/check_env_contract.py --strict)

if is_truthy "$WITH_CORE_SERVICES"; then
  log "Starting core services (postgres/temporal)"
  (cd "$ROOT_DIR" && ./scripts/deploy/core_services.sh up --env-file "$ROOT_DIR/.env") || fail "core services failed"
fi

if command -v psql >/dev/null 2>&1; then
  DB_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@127.0.0.1:${CORE_POSTGRES_PORT}/sourceharbor}"
  PSQL_URL="${DB_URL/postgresql+psycopg:\/\//postgresql://}"
  if [[ "$DB_URL" == postgresql* ]]; then
    DB_NAME="$(python3 - <<'PY'
import os
from urllib.parse import urlparse
core_port = os.getenv('CORE_POSTGRES_PORT', '15432')
u = os.getenv('DATABASE_URL', f'postgresql+psycopg://127.0.0.1:{core_port}/sourceharbor')
u = u.replace('postgresql+psycopg://', 'postgresql://', 1)
path = urlparse(u).path.strip('/')
print(path or 'sourceharbor')
PY
)"
    DB_CONN_JSON="$(PSQL_URL="$PSQL_URL" CORE_POSTGRES_PORT="$CORE_POSTGRES_PORT" python3 - <<'PY'
import json, os
from urllib.parse import urlparse
core_port = os.getenv('CORE_POSTGRES_PORT', '15432')
u = os.getenv('PSQL_URL', f'postgresql://127.0.0.1:{core_port}/sourceharbor')
p = urlparse(u)
print(json.dumps({
  'host': p.hostname or '127.0.0.1',
  'port': p.port or 5432,
  'user': p.username or '',
  'password': p.password or '',
}))
PY
)"
    DB_HOST="$(DB_CONN_JSON="$DB_CONN_JSON" python3 - <<'PY'
import json, os
print(json.loads(os.environ['DB_CONN_JSON'])['host'])
PY
)"
    DB_PORT="$(DB_CONN_JSON="$DB_CONN_JSON" python3 - <<'PY'
import json, os
print(json.loads(os.environ['DB_CONN_JSON'])['port'])
PY
)"
    DB_USER="$(DB_CONN_JSON="$DB_CONN_JSON" python3 - <<'PY'
import json, os
print(json.loads(os.environ['DB_CONN_JSON'])['user'])
PY
)"
    DB_PASSWORD="$(DB_CONN_JSON="$DB_CONN_JSON" python3 - <<'PY'
import json, os
print(json.loads(os.environ['DB_CONN_JSON'])['password'])
PY
)"
    log "Ensuring database exists: ${DB_NAME}"
    if [[ -n "$DB_USER" ]]; then
      PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" 2>/dev/null || true
    else
      createdb "$DB_NAME" 2>/dev/null || true
    fi
    log "Applying SQL migrations"
    apply_psql_migrations "$PSQL_URL" || fail "failed to apply SQL migrations"
  else
    log "Skip psql migrations: DATABASE_URL is not PostgreSQL (${DB_URL})"
  fi
else
  log "Skip psql migrations: psql not found"
fi

if [[ -n "${SQLITE_PATH:-}" ]] && command -v sqlite3 >/dev/null 2>&1; then
  log "Applying SQLite state init"
  sqlite3 "$SQLITE_PATH" < "$ROOT_DIR/infra/sql/sqlite_state_init.sql"
fi

if is_truthy "$WITH_READER_STACK"; then
  command -v docker >/dev/null 2>&1 || fail "reader stack is a Docker-only optional lane; docker not found"
  docker compose version >/dev/null 2>&1 || fail "reader stack is a Docker-only optional lane; docker compose not available"
  docker ps >/dev/null 2>&1 || fail "reader stack is a Docker-only optional lane; docker daemon unavailable"
  if [[ ! -f "$READER_ENV_FILE" ]]; then
    log "Reader env not found, creating template at $READER_ENV_FILE"
    mkdir -p "$(dirname "$READER_ENV_FILE")"
    cp "$READER_ENV_TEMPLATE_FILE" "$READER_ENV_FILE"
    log "Template created. Update credentials in $READER_ENV_FILE before deploy."
  fi
  log "Starting reader stack"
  (cd "$ROOT_DIR" && ./scripts/deploy/reader_stack.sh up --env-file "$READER_ENV_FILE") || fail "reader stack failed"
else
  log "Skipping reader stack; rerun with --with-reader-stack 1 when Docker compose is available"
fi

write_runtime_resolved_env "$ROOT_DIR" "$SCRIPT_NAME" \
  "API_PORT=${API_PORT}" \
  "WEB_PORT=${WEB_PORT}" \
  "SOURCE_HARBOR_API_BASE_URL=${SOURCE_HARBOR_API_BASE_URL}" \
  "NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}" \
  "DATABASE_URL=${DATABASE_URL}" \
  "CORE_POSTGRES_PORT=${CORE_POSTGRES_PORT}" \
  "TEMPORAL_TARGET_HOST=${TEMPORAL_TARGET_HOST}" \
  "TEMPORAL_NAMESPACE=${TEMPORAL_NAMESPACE}" \
  "TEMPORAL_TASK_QUEUE=${TEMPORAL_TASK_QUEUE}"

cat <<EOF
[$SCRIPT_NAME] Bootstrap complete.
[$SCRIPT_NAME] Runtime snapshot: $RESOLVED_ENV_PATH
[$SCRIPT_NAME]   API: ${SOURCE_HARBOR_API_BASE_URL}
[$SCRIPT_NAME]   Web: http://127.0.0.1:${WEB_PORT}
[$SCRIPT_NAME]   Database: ${DATABASE_URL}
[$SCRIPT_NAME]   Temporal queue: ${TEMPORAL_TASK_QUEUE}
[$SCRIPT_NAME]   Reader stack: $(if is_truthy "$WITH_READER_STACK"; then printf 'enabled (%s)' "$READER_ENV_FILE"; else printf 'skipped by default; rerun with --with-reader-stack 1 when Docker compose is available'; fi)
[$SCRIPT_NAME] Next:
[$SCRIPT_NAME]   1) ./bin/full-stack up
[$SCRIPT_NAME]   2) ./scripts/ci/smoke_full_stack.sh
[$SCRIPT_NAME] Optional reader stack docs:
[$SCRIPT_NAME]   docs/deploy/miniflux-nextflux-gce.md
EOF
