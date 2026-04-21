#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="smoke_full_stack"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck source=./scripts/runtime/logging.sh
source "$ROOT_DIR/scripts/runtime/logging.sh"
sourceharbor_log_init "tests" "$SCRIPT_NAME" "$ROOT_DIR/.runtime-cache/logs/tests/smoke-full-stack.jsonl"
ENV_PROFILE="${ENV_PROFILE:-local}"
LIVE_DIAGNOSTICS_JSON=".runtime-cache/reports/tests/e2e-live-smoke-result.json"
API_BASE="http://127.0.0.1:9000"
WEB_BASE="http://127.0.0.1:3001"
API_BASE_EXPLICIT="0"
WEB_BASE_EXPLICIT="0"
REQUIRE_READER="0"
MINIFLUX_BASE=""
NEXTFLUX_PORT="3000"
READER_ENV_TEMPLATE_FILE="$ROOT_DIR/env/profiles/reader.env"
READER_ENV_LOCAL_FILE="$ROOT_DIR/env/profiles/reader.local.env"
if [[ -f "$READER_ENV_LOCAL_FILE" ]]; then
  READER_ENV_FILE="$READER_ENV_LOCAL_FILE"
else
  READER_ENV_FILE="$READER_ENV_TEMPLATE_FILE"
fi
HEARTBEAT_SECONDS="30"
LIVE_SMOKE_API_BASE_URL="http://127.0.0.1:9000"
LIVE_SMOKE_API_BASE_URL_EXPLICIT="0"
LIVE_SMOKE_REQUIRE_API="1"
LIVE_SMOKE_REQUIRE_SECRETS="1"
LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE="0"
LIVE_SMOKE_COMPUTER_USE_STRICT="1"
LIVE_SMOKE_COMPUTER_USE_SKIP="0"
LIVE_SMOKE_COMPUTER_USE_SKIP_REASON=""
YOUTUBE_SMOKE_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
LIVE_SMOKE_BILIBILI_CANARY_MATRIX=""
LIVE_SMOKE_BILIBILI_CANARY_TIER=""
LIVE_SMOKE_BILIBILI_CANARY_LIMIT="0"
LIVE_SMOKE_BILIBILI_READER_RECEIPT_SAMPLE=""
inherited_api_base="${SOURCE_HARBOR_API_BASE_URL-}"
inherited_web_port="${WEB_PORT-}"

usage() {
  cat <<'EOF'
Usage: scripts/ci/smoke_full_stack.sh [options]

Options:
  --profile, --env-profile <name>     Env profile passed to load_repo_env (default: local)
  --api-base-url <url>                API base URL (default: resolved runtime route / .env / 9000)
  --web-base-url <url>                Web base URL (default: resolved WEB_PORT / .env / 3001)
  --require-reader <0|1>              Require reader-stack checks (default: 0)
  --reader-env-file <path>            Reader env file for Miniflux/Nextflux values
                                      (default: reader.local.env when present, else tracked template)
  --heartbeat-seconds <n>             Smoke heartbeat interval (default: 30)
  --offline-fallback <0>             Deprecated compatibility alias used by docs.
                                      Only 0 is accepted; use live-smoke flags for other behavior.
  --live-smoke-api-base-url <url>     e2e live smoke API base URL (default: same as --api-base-url)
  --live-smoke-require-api <0|1>      e2e live smoke require API health gate (default: 1)
  --live-smoke-require-secrets <0|1>  e2e live smoke require secrets (default: 1)
  --live-smoke-require-notification-lane <0|1>
                                      e2e live smoke require notification/provider lane readiness
                                      (default: 0)
  --live-smoke-computer-use-strict <0|1>
                                       e2e live smoke computer-use strict mode (default: 1)
  --live-smoke-computer-use-skip <0|1>
                                       e2e live smoke skip computer-use phase (default: 0)
  --live-smoke-computer-use-skip-reason <text>
                                       e2e live smoke skip reason when skip=1
  --youtube-smoke-url <url>           e2e live smoke YouTube URL
  --live-smoke-bilibili-canary-matrix <path>
                                      e2e live smoke Bilibili canary matrix JSON
  --live-smoke-bilibili-canary-tier <name>
                                      e2e live smoke Bilibili canary tier filter
  --live-smoke-bilibili-canary-limit <n>
                                      e2e live smoke Bilibili canary sample limit
  --live-smoke-bilibili-reader-receipt-sample <slug>
                                      e2e live smoke matrix sample used for manual-intake -> reader receipt
  --live-diagnostics-json <path>      e2e live smoke diagnostics output path
  -h, --help                          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile|--env-profile)
      ENV_PROFILE="${2:-}"
      shift 2
      ;;
    --api-base-url)
      API_BASE="${2:-}"
      API_BASE_EXPLICIT="1"
      shift 2
      ;;
    --web-base-url)
      WEB_BASE="${2:-}"
      WEB_BASE_EXPLICIT="1"
      shift 2
      ;;
    --require-reader)
      REQUIRE_READER="${2:-}"
      shift 2
      ;;
    --reader-env-file)
      READER_ENV_FILE="${2:-}"
      shift 2
      ;;
    --heartbeat-seconds)
      HEARTBEAT_SECONDS="${2:-}"
      shift 2
      ;;
    --offline-fallback)
      if [[ "${2:-}" != "0" ]]; then
        echo "[$SCRIPT_NAME] --offline-fallback only supports 0 for backward-compatible docs usage; use explicit --live-smoke-* flags instead" >&2
        exit 2
      fi
      shift 2
      ;;
    --live-smoke-api-base-url)
      LIVE_SMOKE_API_BASE_URL="${2:-}"
      LIVE_SMOKE_API_BASE_URL_EXPLICIT="1"
      shift 2
      ;;
    --live-smoke-require-api)
      LIVE_SMOKE_REQUIRE_API="${2:-}"
      shift 2
      ;;
    --live-smoke-require-secrets)
      LIVE_SMOKE_REQUIRE_SECRETS="${2:-}"
      shift 2
      ;;
    --live-smoke-require-notification-lane)
      LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE="${2:-}"
      shift 2
      ;;
    --live-smoke-computer-use-strict)
      LIVE_SMOKE_COMPUTER_USE_STRICT="${2:-}"
      shift 2
      ;;
    --live-smoke-computer-use-skip)
      LIVE_SMOKE_COMPUTER_USE_SKIP="${2:-}"
      shift 2
      ;;
    --live-smoke-computer-use-skip-reason)
      LIVE_SMOKE_COMPUTER_USE_SKIP_REASON="${2:-}"
      shift 2
      ;;
    --youtube-smoke-url)
      YOUTUBE_SMOKE_URL="${2:-}"
      shift 2
      ;;
    --live-smoke-bilibili-canary-matrix)
      LIVE_SMOKE_BILIBILI_CANARY_MATRIX="${2:-}"
      shift 2
      ;;
    --live-smoke-bilibili-canary-tier)
      LIVE_SMOKE_BILIBILI_CANARY_TIER="${2:-}"
      shift 2
      ;;
    --live-smoke-bilibili-canary-limit)
      LIVE_SMOKE_BILIBILI_CANARY_LIMIT="${2:-}"
      shift 2
      ;;
    --live-smoke-bilibili-reader-receipt-sample)
      LIVE_SMOKE_BILIBILI_READER_RECEIPT_SAMPLE="${2:-}"
      shift 2
      ;;
    --live-diagnostics-json)
      LIVE_DIAGNOSTICS_JSON="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "[$SCRIPT_NAME] unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# shellcheck source=./scripts/lib/load_env.sh
source "$ROOT_DIR/scripts/lib/load_env.sh"
load_repo_env "$ROOT_DIR" "$SCRIPT_NAME" "$ENV_PROFILE"

resolve_route_value_local() {
  local key="$1"
  local cli_value="$2"
  local default_value="$3"
  if declare -F resolve_runtime_route_value >/dev/null 2>&1; then
    resolve_runtime_route_value "$ROOT_DIR" "$key" "$cli_value" "$default_value"
    return 0
  fi
  if [[ -n "$cli_value" ]]; then
    printf '%s\n' "$cli_value"
    return 0
  fi
  local current_value
  current_value="${!key:-}"
  if [[ -n "$current_value" ]]; then
    printf '%s\n' "$current_value"
    return 0
  fi
  printf '%s\n' "$default_value"
}

api_base_cli=""
if [[ "$API_BASE_EXPLICIT" == "1" ]]; then
  api_base_cli="$API_BASE"
fi
API_BASE="$(
  resolve_runtime_route_value_with_sources \
    "$ROOT_DIR" \
    "SOURCE_HARBOR_API_BASE_URL" \
    "$api_base_cli" \
    "$inherited_api_base" \
    "${SOURCE_HARBOR_API_BASE_URL:-}" \
    "http://127.0.0.1:9000"
)"

if [[ "$WEB_BASE_EXPLICIT" != "1" ]]; then
  resolved_web_port="$(
    resolve_runtime_route_value_with_sources \
      "$ROOT_DIR" \
      "WEB_PORT" \
      "" \
      "$inherited_web_port" \
      "${WEB_PORT:-}" \
      "3001"
  )"
  WEB_BASE="http://127.0.0.1:${resolved_web_port}"
fi
if [[ "$LIVE_SMOKE_API_BASE_URL_EXPLICIT" != "1" ]]; then
  LIVE_SMOKE_API_BASE_URL="$API_BASE"
fi

MINIFLUX_BASE="${MINIFLUX_BASE_URL:-$MINIFLUX_BASE}"
NEXTFLUX_PORT="${NEXTFLUX_PORT:-$NEXTFLUX_PORT}"
heartbeat_pid=""
AI_FEED_SYNC_TMP_OUTPUT=""

log() { sourceharbor_log info smoke_full_stack "$*"; }
fail() { sourceharbor_log error smoke_full_stack_error "$*"; exit 1; }

is_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

check_http_200() {
  local url="$1"
  local code attempt
  for attempt in $(seq 1 40); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" || true)"
    if [[ "$code" == "200" ]]; then
      return 0
    fi
    sleep 1
  done
  fail "http check failed: ${url} -> ${code}"
}

start_heartbeat() {
  local label="$1"
  (
    while true; do
      log "heartbeat: ${label} still running..."
      sleep "$HEARTBEAT_SECONDS"
    done
  ) &
  heartbeat_pid="$!"
}

stop_heartbeat() {
  if [[ -n "$heartbeat_pid" ]] && kill -0 "$heartbeat_pid" >/dev/null 2>&1; then
    kill "$heartbeat_pid" >/dev/null 2>&1 || true
    wait "$heartbeat_pid" 2>/dev/null || true
  fi
  heartbeat_pid=""
}

cleanup_temp_files() {
  if [[ -n "$AI_FEED_SYNC_TMP_OUTPUT" ]] && [[ -f "$AI_FEED_SYNC_TMP_OUTPUT" ]]; then
    rm -f "$AI_FEED_SYNC_TMP_OUTPUT"
  fi
}

cleanup() {
  stop_heartbeat
  cleanup_temp_files
}
trap cleanup EXIT

log "phase=short_tests status=start"
log "Checking API health"
check_http_200 "${API_BASE}/healthz"

log "Checking feed API"
check_http_200 "${API_BASE}/api/v1/feed/digests?limit=1"

log "Checking web UI"
check_http_200 "${WEB_BASE}"
log "phase=short_tests status=passed"

log "phase=long_tests status=start"
log "Running built-in e2e live smoke"
start_heartbeat "e2e_live_smoke"
live_smoke_extra_args=()
if [[ -n "$LIVE_SMOKE_BILIBILI_CANARY_MATRIX" ]]; then
  live_smoke_extra_args+=(--bilibili-canary-matrix "$LIVE_SMOKE_BILIBILI_CANARY_MATRIX")
fi
if [[ -n "$LIVE_SMOKE_BILIBILI_CANARY_TIER" ]]; then
  live_smoke_extra_args+=(--bilibili-canary-tier "$LIVE_SMOKE_BILIBILI_CANARY_TIER")
fi
if [[ -n "$LIVE_SMOKE_BILIBILI_CANARY_LIMIT" ]]; then
  live_smoke_extra_args+=(--bilibili-canary-limit "$LIVE_SMOKE_BILIBILI_CANARY_LIMIT")
fi
if [[ -n "$LIVE_SMOKE_BILIBILI_READER_RECEIPT_SAMPLE" ]]; then
  live_smoke_extra_args+=(--bilibili-reader-receipt-sample "$LIVE_SMOKE_BILIBILI_READER_RECEIPT_SAMPLE")
fi
if ! (cd "$ROOT_DIR" && ./scripts/ci/e2e_live_smoke.sh \
  --profile "$ENV_PROFILE" \
  --api-base-url "$LIVE_SMOKE_API_BASE_URL" \
  --require-api "$LIVE_SMOKE_REQUIRE_API" \
  --require-secrets "$LIVE_SMOKE_REQUIRE_SECRETS" \
  --require-notification-lane "$LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE" \
  --computer-use-strict "$LIVE_SMOKE_COMPUTER_USE_STRICT" \
  --computer-use-skip "$LIVE_SMOKE_COMPUTER_USE_SKIP" \
  --computer-use-skip-reason "$LIVE_SMOKE_COMPUTER_USE_SKIP_REASON" \
  --youtube-url "$YOUTUBE_SMOKE_URL" \
  --diagnostics-json "$LIVE_DIAGNOSTICS_JSON" \
  "${live_smoke_extra_args[@]}"); then
  stop_heartbeat
  live_diag_path="$ROOT_DIR/$LIVE_DIAGNOSTICS_JSON"
  if [[ -f "$live_diag_path" ]]; then
    diag_summary="$(
      DIAG_PATH="$live_diag_path" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["DIAG_PATH"])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("failure_kind=unknown reason=diagnostics_parse_failed")
    raise SystemExit(0)
print(
    "failure_kind={kind} reason={reason}".format(
        kind=payload.get("failure_kind", "unknown"),
        reason=payload.get("reason", ""),
    )
)
PY
    )"
    log "e2e_live_smoke failed: ${diag_summary} diagnostics_path=${live_diag_path}"
  else
    log "e2e_live_smoke failed: diagnostics missing at ${live_diag_path}"
  fi
  fail "live smoke failed"
fi
stop_heartbeat
log "e2e_live_smoke diagnostics_path=$ROOT_DIR/$LIVE_DIAGNOSTICS_JSON"

if is_truthy "$REQUIRE_READER"; then
  if [[ -z "$MINIFLUX_BASE" && -f "$READER_ENV_FILE" ]]; then
    load_env_file_preserve_process_env "$READER_ENV_FILE" "$SCRIPT_NAME"
    MINIFLUX_BASE="${MINIFLUX_BASE_URL:-}"
    NEXTFLUX_PORT="${NEXTFLUX_PORT:-3000}"
  fi
  if [[ -z "$MINIFLUX_BASE" ]]; then
    fail "--require-reader=1 but MINIFLUX_BASE_URL is empty"
  fi
  log "Checking Miniflux"
  check_http_200 "$MINIFLUX_BASE"
  nextflux_base="http://127.0.0.1:${NEXTFLUX_PORT}"
  log "Checking Nextflux"
  check_http_200 "$nextflux_base"

  log "Running AI feed -> Miniflux sync"
  AI_FEED_SYNC_TMP_OUTPUT="$(mktemp)"
  start_heartbeat "run_ai_feed_sync"
  (cd "$ROOT_DIR" && ./scripts/runtime/run_ai_feed_sync.sh \
    --profile "$ENV_PROFILE" \
    --reader-env-file "$READER_ENV_FILE" \
    --api-base-url "$API_BASE" \
    --miniflux-base-url "$MINIFLUX_BASE" >"$AI_FEED_SYNC_TMP_OUTPUT")
  stop_heartbeat
  log "AI feed sync result: $(cat "$AI_FEED_SYNC_TMP_OUTPUT")"
  cleanup_temp_files
  AI_FEED_SYNC_TMP_OUTPUT=""
fi

log "phase=long_tests status=passed"
log "Smoke checks passed"
