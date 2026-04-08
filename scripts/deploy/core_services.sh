#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/compose/core-services.compose.yml"
ENV_FILE="$ROOT_DIR/.env"

eval "$(python3 "$ROOT_DIR/scripts/ci/contract.py" shell-exports)"

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy/core_services.sh [up|down|restart|status|logs] [--env-file <path>]

SourceHarbor local core services compose helper.
Starts or inspects the repo-local Postgres + Temporal stack from
infra/compose/core-services.compose.yml.
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

command -v docker >/dev/null 2>&1 || { echo "docker not found" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "docker compose not available" >&2; exit 1; }

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

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
