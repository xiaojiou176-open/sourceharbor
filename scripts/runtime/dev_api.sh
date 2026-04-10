#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=./scripts/lib/load_env.sh
source "$ROOT_DIR/scripts/lib/load_env.sh"
# shellcheck source=./scripts/lib/standard_env.sh
source "$ROOT_DIR/scripts/lib/standard_env.sh"
load_repo_env "$ROOT_DIR" "dev_api"
ensure_external_uv_project_environment "$ROOT_DIR"
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"

if [[ -z "${SOURCE_HARBOR_API_KEY:-}" && -z "${CI:-}" && -z "${GITHUB_ACTIONS:-}" ]]; then
  export SOURCE_HARBOR_API_KEY="sourceharbor-local-dev-token"
fi
if [[ -z "${WEB_ACTION_SESSION_TOKEN:-}" && -n "${SOURCE_HARBOR_API_KEY:-}" ]]; then
  export WEB_ACTION_SESSION_TOKEN="$SOURCE_HARBOR_API_KEY"
fi

API_APP="apps.api.app.main:app"
API_HOST="127.0.0.1"
API_PORT="9000"
ENABLE_RELOAD=1

usage() {
  cat <<'EOF'
Usage: ./bin/dev-api [--app <module:app>] [--host <host>] [--port <port>] [--reload|--no-reload]

Options:
  --app <module:app>  Uvicorn ASGI app target (default: apps.api.app.main:app)
  --host <host>       Uvicorn bind host (default: 127.0.0.1)
  --port <port>       Uvicorn bind port (default: 9000)
  --reload            Enable auto-reload (default)
  --no-reload         Disable auto-reload
  -h, --help          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "[dev_api] --app requires a non-empty value" >&2
        exit 2
      fi
      API_APP="$2"
      shift 2
      ;;
    --host)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "[dev_api] --host requires a non-empty value" >&2
        exit 2
      fi
      API_HOST="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "[dev_api] --port requires a non-empty value" >&2
        exit 2
      fi
      API_PORT="$2"
      shift 2
      ;;
    --reload)
      ENABLE_RELOAD=1
      shift
      ;;
    --no-reload)
      ENABLE_RELOAD=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[dev_api] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$API_PORT" =~ ^[0-9]+$ ]] || (( API_PORT <= 0 || API_PORT > 65535 )); then
  echo "[dev_api] --port must be an integer in [1,65535]" >&2
  exit 2
fi

if [[ ! -d "$ROOT_DIR/apps/api" ]]; then
  echo "[dev_api] API directory not found: $ROOT_DIR/apps/api" >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/apps/worker:$ROOT_DIR:${PYTHONPATH:-}"
cd "$ROOT_DIR"

uvicorn_args=("$API_APP" "--host" "$API_HOST" "--port" "$API_PORT")
if [[ "$ENABLE_RELOAD" == "1" ]]; then
  uvicorn_args+=("--reload")
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run uvicorn "${uvicorn_args[@]}"
fi

exec python -m uvicorn "${uvicorn_args[@]}"
