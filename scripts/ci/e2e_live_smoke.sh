#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="e2e_live_smoke"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck source=./scripts/runtime/logging.sh
source "$ROOT_DIR/scripts/runtime/logging.sh"
sourceharbor_log_init "tests" "$SCRIPT_NAME" "$ROOT_DIR/.runtime-cache/logs/tests/e2e-live-smoke.jsonl"
ENV_PROFILE="${ENV_PROFILE:-local}"
CLI_LIVE_SMOKE_API_BASE_URL="http://127.0.0.1:9000"
LIVE_SMOKE_REQUIRE_API="1"
LIVE_SMOKE_COMPUTER_USE_STRICT="1"
LIVE_SMOKE_COMPUTER_USE_SKIP="0"
LIVE_SMOKE_COMPUTER_USE_SKIP_REASON=""
LIVE_SMOKE_REQUIRE_SECRETS="1"
LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE="0"
YOUTUBE_SMOKE_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
LIVE_SMOKE_TIMEOUT_SECONDS="180"
LIVE_SMOKE_POLL_INTERVAL_SECONDS="3"
LIVE_SMOKE_HEARTBEAT_SECONDS="30"
live_smoke_health_path="/healthz"
LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS="20"
LIVE_SMOKE_MAX_RETRIES="2"
live_smoke_diagnostics_json=".runtime-cache/reports/tests/e2e-live-smoke-result.json"
LIVE_SMOKE_COMPUTER_USE_CMD=""
BILIBILI_SMOKE_URL="https://www.bilibili.com/video/BV1xx411c7mD"
NOTIFICATION_LANE_READY="1"
NOTIFICATION_LANE_REASON=""

usage() {
  cat <<'EOF'
Usage: scripts/ci/e2e_live_smoke.sh [options]

Options:
  --profile, --env-profile <name>             Env profile passed to load_repo_env (default: local)
  --api-base-url <url>                        API base URL override
  --require-api <0|1>                         Require API health check (default: 1)
  --require-secrets <0|1>                     Require secrets gate (default: 1)
  --require-notification-lane <0|1>           Require notification/provider lane readiness (default: 0)
  --computer-use-strict <0|1>                 Strict computer-use validation (default: 1)
  --computer-use-skip <0|1>                   Skip computer-use phase (default: 0)
  --computer-use-skip-reason <text>           Skip reason when --computer-use-skip=1
  --timeout-seconds <n>                       Live smoke timeout seconds (default: 180)
  --poll-interval-seconds <n>                 Poll interval seconds (default: 3)
  --heartbeat-seconds <n>                     Heartbeat interval seconds (default: 30)
  --health-path <path>                        Health endpoint path (default: /healthz)
  --external-probe-timeout-seconds <n>        External probe timeout seconds (default: 20)
  --max-retries <n>                           Curl retries in [1,2] (default: 2)
  --diagnostics-json <path>                   Diagnostics JSON path (default: .runtime-cache/reports/tests/e2e-live-smoke-result.json)
  --computer-use-cmd <cmd_or_path>            computer_use smoke command override
  --youtube-url <url>                         YouTube URL used in probes/process (default: dQw4w9WgXcQ)
  --bilibili-url <url>                        Bilibili URL used in probes/process (default: BV1xx411c7mD)
  -h, --help                                  Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile|--env-profile)
      ENV_PROFILE="${2:-}"
      shift 2
      ;;
    --api-base-url)
      CLI_LIVE_SMOKE_API_BASE_URL="${2:-}"
      shift 2
      ;;
    --require-api)
      LIVE_SMOKE_REQUIRE_API="${2:-}"
      shift 2
      ;;
    --require-secrets)
      LIVE_SMOKE_REQUIRE_SECRETS="${2:-}"
      shift 2
      ;;
    --require-notification-lane)
      LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE="${2:-}"
      shift 2
      ;;
    --computer-use-strict)
      LIVE_SMOKE_COMPUTER_USE_STRICT="${2:-}"
      shift 2
      ;;
    --computer-use-skip)
      LIVE_SMOKE_COMPUTER_USE_SKIP="${2:-}"
      shift 2
      ;;
    --computer-use-skip-reason)
      LIVE_SMOKE_COMPUTER_USE_SKIP_REASON="${2:-}"
      shift 2
      ;;
    --timeout-seconds)
      LIVE_SMOKE_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --poll-interval-seconds)
      LIVE_SMOKE_POLL_INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    --heartbeat-seconds)
      LIVE_SMOKE_HEARTBEAT_SECONDS="${2:-}"
      shift 2
      ;;
    --health-path)
      live_smoke_health_path="${2:-}"
      shift 2
      ;;
    --external-probe-timeout-seconds)
      LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --max-retries)
      LIVE_SMOKE_MAX_RETRIES="${2:-}"
      shift 2
      ;;
    --diagnostics-json)
      live_smoke_diagnostics_json="${2:-}"
      shift 2
      ;;
    --computer-use-cmd)
      LIVE_SMOKE_COMPUTER_USE_CMD="${2:-}"
      shift 2
      ;;
    --youtube-url)
      YOUTUBE_SMOKE_URL="${2:-}"
      shift 2
      ;;
    --bilibili-url)
      BILIBILI_SMOKE_URL="${2:-}"
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

LIVE_SMOKE_API_BASE_URL="$CLI_LIVE_SMOKE_API_BASE_URL"
API_BASE_URL="$LIVE_SMOKE_API_BASE_URL"
DIAGNOSTICS_PATH=""
SCENARIO_TRACE=""
WRITE_OP_TRACE=""
TEARDOWN_TRACE=""
YOUTUBE_KEY_RESOLUTION_TRACE=""
TEARDOWN_DONE=0
LONG_PHASE_HEARTBEAT_PID=""
WORKER_TMP_OUTPUTS=()
SMOKE_TMP_FILES=()
STARTED_AT_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
FAILURE_KIND="unknown"
if [[ "${live_smoke_diagnostics_json:0:1}" != "/" ]]; then
  DIAGNOSTICS_PATH="$ROOT_DIR/$live_smoke_diagnostics_json"
else
  DIAGNOSTICS_PATH="$live_smoke_diagnostics_json"
fi

log() {
  sourceharbor_log info e2e_live_smoke "$*"
}

fail() {
  FAILURE_KIND="$(classify_failure "$*")"
  stop_long_phase_heartbeat
  run_teardown
  write_diagnostics "failed" "$*"
  sourceharbor_log error e2e_live_smoke_error "$*"
  sourceharbor_log error e2e_live_smoke_failure_kind "failure_kind=${FAILURE_KIND} diagnostics_path=${DIAGNOSTICS_PATH}"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

is_truthy() {
  local value
  value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

require_enum() {
  local name="$1"
  local value="$2"
  shift 2
  local allowed=("$@")
  local candidate
  for candidate in "${allowed[@]}"; do
    if [[ "$value" == "$candidate" ]]; then
      return 0
    fi
  done
  fail "invalid ${name}=${value}; allowed: ${allowed[*]}"
}

trim_whitespace() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

classify_failure() {
  local reason
  reason="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  case "$reason" in
    *timeout*|*timed*out*|*unreachable*|*external*probe*failed*|*curl*exit*|*connection*|*api*health*check*failed*)
      printf '%s' "network_or_environment_timeout"
      ;;
    *)
      printf '%s' "code_logic_error"
      ;;
  esac
}

mask_secret() {
  local value="${1:-}"
  local len="${#value}"
  if (( len <= 8 )); then
    printf '%s' "***"
    return 0
  fi
  printf '%s...%s' "${value:0:4}" "${value:len-4:4}"
}

read_key_from_env_file() {
  local file_path="$1"
  local var_name="$2"
  [[ -f "$file_path" ]] || return 1

  local key_value
  key_value="$(
    FILE_PATH="$file_path" VAR_NAME="$var_name" python3 - <<'PY'
import os
import re
import shlex
from pathlib import Path

file_path = Path(os.environ["FILE_PATH"])
var_name = os.environ["VAR_NAME"]
pattern = re.compile(r"^\s*(?:export\s+)?%s\s*=\s*(.+?)\s*$" % re.escape(var_name))
result = ""

for line in file_path.read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    match = pattern.match(line)
    if not match:
        continue
    raw = match.group(1).strip()
    if raw:
        if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
            try:
                parsed = shlex.split(f"x={raw}", posix=True)
                if parsed and "=" in parsed[0]:
                    raw = parsed[0].split("=", 1)[1]
            except ValueError:
                raw = raw[1:-1]
        result = raw

if result:
    print(result)
PY
  )"
  key_value="$(trim_whitespace "$key_value")"
  [[ -n "$key_value" ]] || return 1
  printf '%s' "$key_value"
}

write_key_to_env_file() {
  local env_path="$1"
  local var_name="$2"
  local var_value="$3"
  [[ -n "$env_path" ]] || fail "cannot write ${var_name}: empty env path"

  ENV_PATH="$env_path" VAR_NAME="$var_name" VAR_VALUE="$var_value" python3 - <<'PY'
import os
import re
from pathlib import Path

env_path = Path(os.environ["ENV_PATH"])
var_name = os.environ["VAR_NAME"]
var_value = os.environ["VAR_VALUE"]
pattern = re.compile(r"^(\s*(?:export\s+)?)%s\s*=.*$" % re.escape(var_name))

if env_path.exists():
    lines = env_path.read_text(encoding="utf-8").splitlines()
else:
    lines = []

def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"

new_line = f"export {var_name}={shell_quote(var_value)}"
updated = False
for idx, line in enumerate(lines):
    if pattern.match(line):
        lines[idx] = new_line
        updated = True
        break

if not updated:
    lines.append(new_line)

content = "\n".join(lines).rstrip() + "\n"
env_path.write_text(content, encoding="utf-8")
PY
}

probe_youtube_key() {
  local key_value="$1"
  local tmp_file
  tmp_file="$(mktemp)"
  local status curl_exit
  curl_exit=0
  status="$(
    curl -sS -o "$tmp_file" -w '%{http_code}' \
      --max-time "$LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS" \
      --retry "$((LIVE_SMOKE_MAX_RETRIES - 1))" --retry-delay 1 --retry-all-errors \
      "https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ&maxResults=1&key=${key_value}"
  )" || curl_exit=$?
  local body
  body="$(cat "$tmp_file" 2>/dev/null || true)"
  rm -f "$tmp_file"

  if [[ "$curl_exit" -ne 0 ]]; then
    printf '%s\t%s\t%s\n' "transport_error" "$status" "$curl_exit"
    return 2
  fi
  if [[ "$status" == "200" ]]; then
    printf '%s\t%s\t%s\n' "valid" "$status" "0"
    return 0
  fi

  local reason="invalid_or_restricted"
  local lowered
  lowered="$(printf '%s' "$body" | tr '[:upper:]' '[:lower:]')"
  case "$lowered" in
    *apikeynotvalid*|*badrequest*|*invalid*api*key*|*key*invalid*)
      reason="invalid_key"
      ;;
    *accessnotconfigured*|*forbidden*|*permission*|*quota*)
      reason="quota_or_permission"
      ;;
  esac
  printf '%s\t%s\t%s\n' "$reason" "$status" "0"
  return 1
}

record_youtube_key_resolution() {
  local source_name="$1"
  local status="$2"
  local detail="${3:-}"
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local line
  line="$(printf '%s\t%s\t%s\t%s\n' "$ts" "$source_name" "$status" "$detail")"
  YOUTUBE_KEY_RESOLUTION_TRACE+="${line}"$'\n'
}

ensure_valid_youtube_api_key() {
  local repo_env_file="$ROOT_DIR/.env"
  local -a candidates=()
  local -a labels=()
  local candidate label masked probe_result reason status_code curl_exit

  add_candidate() {
    local value="${1:-}"
    local source="${2:-unknown}"
    value="$(trim_whitespace "$value")"
    [[ -n "$value" ]] || return 0
    candidates+=("$value")
    labels+=("$source")
  }

  add_candidate "${YOUTUBE_API_KEY:-}" ".env_or_shell_current"
  add_candidate "$(read_key_from_env_file "$ROOT_DIR/.env" "YOUTUBE_API_KEY" || true)" ".env_file"

  if [[ "${#candidates[@]}" -eq 0 ]]; then
    fail "YOUTUBE_API_KEY is missing in .env/current-shell; provide a valid key before running live smoke"
  fi

  for idx in "${!candidates[@]}"; do
    candidate="${candidates[$idx]}"
    label="${labels[$idx]}"
    masked="$(mask_secret "$candidate")"
    probe_result="$(probe_youtube_key "$candidate")" || true
    reason="${probe_result%%$'\t'*}"
    probe_result="${probe_result#*$'\t'}"
    status_code="${probe_result%%$'\t'*}"
    curl_exit="${probe_result#*$'\t'}"

    if [[ "$reason" == "valid" ]]; then
      YOUTUBE_API_KEY="$candidate"
      export YOUTUBE_API_KEY
      record_youtube_key_resolution "$label" "valid" "status=${status_code} masked=${masked}"
      log "YOUTUBE_API_KEY validated from ${label} (${masked})"
      if [[ "$label" != ".env_or_shell_current" && -f "$repo_env_file" ]]; then
        write_key_to_env_file "$repo_env_file" "YOUTUBE_API_KEY" "$candidate"
        record_write_operation \
          "repair_env_youtube_api_key" \
          "env:youtube_api_key:${label}" \
          "persist valid key into .env for deterministic next runs" \
          "source=${label} masked=${masked}"
        log "YOUTUBE_API_KEY repaired from ${label} and persisted to .env"
      fi
      return 0
    fi

    record_youtube_key_resolution "$label" "invalid" "reason=${reason} status=${status_code} curl_exit=${curl_exit} masked=${masked}"
    log "YOUTUBE_API_KEY rejected from ${label} (${masked}) reason=${reason} status=${status_code} curl_exit=${curl_exit}"
    if [[ "$reason" == "transport_error" ]]; then
      fail "external probe failed while validating YOUTUBE_API_KEY from ${label}: status=${status_code} curl_exit=${curl_exit}"
    fi
  done

  fail "YOUTUBE_API_KEY is invalid after probing .env/current-shell candidates; provide a valid key before running live smoke"
}

record_scenario() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local line
  line="$(printf '%s\t%s\t%s\t%s\n' "$ts" "$name" "$status" "$detail")"
  SCENARIO_TRACE+="${line}"$'\n'
}

record_write_operation() {
  local name="$1"
  local idempotency_key="$2"
  local cleanup_action="$3"
  local detail="${4:-}"
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local line
  line="$(printf '%s\t%s\t%s\t%s\t%s\n' "$ts" "$name" "$idempotency_key" "$cleanup_action" "$detail")"
  WRITE_OP_TRACE+="${line}"$'\n'
}

record_teardown_step() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local line
  line="$(printf '%s\t%s\t%s\t%s\n' "$ts" "$name" "$status" "$detail")"
  TEARDOWN_TRACE+="${line}"$'\n'
}

run_teardown() {
  if [[ "$TEARDOWN_DONE" == "1" ]]; then
    return 0
  fi
  TEARDOWN_DONE=1
  log "phase=teardown status=start"
  local removed=0
  local output_file
  local tmp_file
  if [[ "${#WORKER_TMP_OUTPUTS[@]}" -eq 0 ]]; then
    record_teardown_step "remove_worker_tmp_output" "skipped" "no temp outputs registered"
  else
    for output_file in "${WORKER_TMP_OUTPUTS[@]}"; do
      if [[ -f "$output_file" ]]; then
        rm -f "$output_file"
        ((removed += 1))
        record_teardown_step "remove_worker_tmp_output" "passed" "path=${output_file}"
      else
        record_teardown_step "remove_worker_tmp_output" "skipped" "path=${output_file} missing"
      fi
    done
  fi
  if [[ "${#SMOKE_TMP_FILES[@]}" -eq 0 ]]; then
    record_teardown_step "remove_smoke_tmp_file" "skipped" "no smoke temp files registered"
  else
    for tmp_file in "${SMOKE_TMP_FILES[@]}"; do
      if [[ -f "$tmp_file" ]]; then
        rm -f "$tmp_file"
        ((removed += 1))
        record_teardown_step "remove_smoke_tmp_file" "passed" "path=${tmp_file}"
      else
        record_teardown_step "remove_smoke_tmp_file" "skipped" "path=${tmp_file} missing"
      fi
    done
  fi
  record_scenario "teardown" "passed" "removed_worker_tmp_outputs=${removed}"
  log "phase=teardown status=passed removed_worker_tmp_outputs=${removed}"
}

start_long_phase_heartbeat() {
  local label="$1"
  stop_long_phase_heartbeat
  (
    while true; do
      log "heartbeat: phase=long_tests step=${label} still running..."
      sleep "$LIVE_SMOKE_HEARTBEAT_SECONDS"
    done
  ) &
  LONG_PHASE_HEARTBEAT_PID="$!"
}

stop_long_phase_heartbeat() {
  if [[ -n "$LONG_PHASE_HEARTBEAT_PID" ]] && kill -0 "$LONG_PHASE_HEARTBEAT_PID" >/dev/null 2>&1; then
    kill "$LONG_PHASE_HEARTBEAT_PID" >/dev/null 2>&1 || true
    wait "$LONG_PHASE_HEARTBEAT_PID" 2>/dev/null || true
  fi
  LONG_PHASE_HEARTBEAT_PID=""
}

write_diagnostics() {
  local status="$1"
  local reason="${2:-}"
  local finished_at
  finished_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  mkdir -p "$(dirname "$DIAGNOSTICS_PATH")"

  STATUS="$status" \
  FAILURE_KIND="$FAILURE_KIND" \
  REASON="$reason" \
  DIAGNOSTICS_PATH="$DIAGNOSTICS_PATH" \
  STARTED_AT_UTC="$STARTED_AT_UTC" \
  FINISHED_AT_UTC="$finished_at" \
  API_BASE_URL="$API_BASE_URL" \
  TIMEOUT_SECONDS="$LIVE_SMOKE_TIMEOUT_SECONDS" \
  HEARTBEAT_SECONDS="$LIVE_SMOKE_HEARTBEAT_SECONDS" \
  SCENARIO_TRACE="$SCENARIO_TRACE" \
  WRITE_OP_TRACE="$WRITE_OP_TRACE" \
  TEARDOWN_TRACE="$TEARDOWN_TRACE" \
  YOUTUBE_KEY_RESOLUTION_TRACE="$YOUTUBE_KEY_RESOLUTION_TRACE" \
  MAX_RETRIES="$LIVE_SMOKE_MAX_RETRIES" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

entries = []
for raw in (os.environ.get("SCENARIO_TRACE", "") or "").splitlines():
    parts = raw.split("\t", 3)
    if len(parts) != 4:
        continue
    ts, name, status, detail = parts
    entries.append(
        {
            "timestamp": ts,
            "scenario": name,
            "status": status,
            "detail": detail,
        }
    )

write_ops = []
for raw in (os.environ.get("WRITE_OP_TRACE", "") or "").splitlines():
    parts = raw.split("\t", 4)
    if len(parts) != 5:
        continue
    ts, name, idempotency_key, cleanup_action, detail = parts
    write_ops.append(
        {
            "timestamp": ts,
            "operation": name,
            "idempotency_key": idempotency_key,
            "cleanup_action": cleanup_action,
            "detail": detail,
        }
    )

teardown_steps = []
for raw in (os.environ.get("TEARDOWN_TRACE", "") or "").splitlines():
    parts = raw.split("\t", 3)
    if len(parts) != 4:
        continue
    ts, name, status, detail = parts
    teardown_steps.append(
        {
            "timestamp": ts,
            "step": name,
            "status": status,
            "detail": detail,
        }
    )

youtube_key_resolution = []
for raw in (os.environ.get("YOUTUBE_KEY_RESOLUTION_TRACE", "") or "").splitlines():
    parts = raw.split("\t", 3)
    if len(parts) != 4:
        continue
    ts, source_name, status, detail = parts
    youtube_key_resolution.append(
        {
            "timestamp": ts,
            "source": source_name,
            "status": status,
            "detail": detail,
        }
    )

payload = {
    "status": os.environ.get("STATUS", "failed"),
    "failure_kind": os.environ.get("FAILURE_KIND", "unknown"),
    "reason": os.environ.get("REASON", ""),
    "api_base_url": os.environ.get("API_BASE_URL", ""),
    "started_at_utc": os.environ.get("STARTED_AT_UTC", ""),
    "finished_at_utc": os.environ.get("FINISHED_AT_UTC", ""),
    "timeout_seconds": int(os.environ.get("TIMEOUT_SECONDS", "0") or "0"),
    "heartbeat_seconds": int(os.environ.get("HEARTBEAT_SECONDS", "0") or "0"),
    "retry_policy": {"max_attempts": int(os.environ.get("MAX_RETRIES", "2") or "2")},
    "write_policy": {
        "idempotency": "each live write operation includes a deterministic idempotency key in write_operations",
        "teardown": "safe teardown removes only this script's temporary files and keeps business records intact",
    },
    "scenarios": entries,
    "write_operations": write_ops,
    "teardown": {"steps": teardown_steps},
    "youtube_key_resolution": youtube_key_resolution,
    "diagnostics_path": os.environ.get("DIAGNOSTICS_PATH", ""),
}

Path(os.environ["DIAGNOSTICS_PATH"]).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
}

resolve_local_script_path() {
  local raw_path="$1"
  local candidate
  candidate="$(trim_whitespace "$raw_path")"
  [[ -n "$candidate" ]] || fail "script path is empty"

  if [[ "${candidate:0:1}" != "/" ]]; then
    candidate="$ROOT_DIR/$candidate"
  fi

  local resolved
  resolved="$(
    SCRIPT_PATH="$candidate" python3 - <<'PY'
import os
import pathlib

path = pathlib.Path(os.environ["SCRIPT_PATH"]).expanduser()
print(path.resolve())
PY
  )"

  case "$resolved" in
    "$ROOT_DIR/scripts/"*) ;;
    *)
      fail "script path must be under $ROOT_DIR/scripts: $resolved"
      ;;
  esac
  [[ -f "$resolved" ]] || fail "script file not found: $resolved"
  [[ -x "$resolved" ]] || fail "script file is not executable: $resolved"
  printf '%s' "$resolved"
}

resolve_local_web_session_token() {
  if [[ -n "${WEB_ACTION_SESSION_TOKEN:-}" ]]; then
    printf '%s' "$WEB_ACTION_SESSION_TOKEN"
    return 0
  fi
  printf ''
}

resolve_local_api_write_token() {
  if [[ -n "${SOURCE_HARBOR_API_KEY:-}" ]]; then
    printf '%s' "$SOURCE_HARBOR_API_KEY"
    return 0
  fi
  if [[ -z "${CI:-}" && -z "${GITHUB_ACTIONS:-}" ]]; then
    printf 'sourceharbor-local-dev-token'
    return 0
  fi
  printf ''
}

api_post() {
  local path="$1"
  local payload="$2"
  local tmp_body
  tmp_body="$(mktemp)"
  local -a auth_headers=()
  local write_token web_session_token
  write_token="$(resolve_local_api_write_token)"
  web_session_token="$(resolve_local_web_session_token)"
  if [[ -n "$write_token" ]]; then
    auth_headers+=(-H "X-API-Key: ${write_token}")
    auth_headers+=(-H "Authorization: Bearer ${write_token}")
  fi
  if [[ -n "$web_session_token" ]]; then
    auth_headers+=(-H "X-Web-Session: ${web_session_token}")
  fi
  local status
  status="$(
    curl -sS -o "$tmp_body" -w '%{http_code}' \
      --retry "$((LIVE_SMOKE_MAX_RETRIES - 1))" --retry-delay 1 --retry-all-errors \
      -H 'Accept: application/json' \
      -H 'Content-Type: application/json' \
      "${auth_headers[@]}" \
      -X POST "${API_BASE_URL}${path}" \
      --data "$payload"
  )"
  local body
  body="$(cat "$tmp_body")"
  rm -f "$tmp_body"
  printf '%s\n%s' "$status" "$body"
}

api_get() {
  local path="$1"
  local tmp_body
  tmp_body="$(mktemp)"
  local -a auth_headers=()
  local write_token web_session_token
  write_token="$(resolve_local_api_write_token)"
  web_session_token="$(resolve_local_web_session_token)"
  if [[ -n "$write_token" ]]; then
    auth_headers+=(-H "X-API-Key: ${write_token}")
    auth_headers+=(-H "Authorization: Bearer ${write_token}")
  fi
  if [[ -n "$web_session_token" ]]; then
    auth_headers+=(-H "X-Web-Session: ${web_session_token}")
  fi
  local status
  status="$(
    curl -sS -o "$tmp_body" -w '%{http_code}' \
      --retry "$((LIVE_SMOKE_MAX_RETRIES - 1))" --retry-delay 1 --retry-all-errors \
      -H 'Accept: application/json' \
      "${auth_headers[@]}" \
      "${API_BASE_URL}${path}"
  )"
  local body
  body="$(cat "$tmp_body")"
  rm -f "$tmp_body"
  printf '%s\n%s' "$status" "$body"
}

check_prerequisites() {
  require_cmd curl
  require_cmd python3

  if ! [[ "$LIVE_SMOKE_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( LIVE_SMOKE_TIMEOUT_SECONDS <= 0 )); then
    fail "invalid --timeout-seconds=${LIVE_SMOKE_TIMEOUT_SECONDS}; expected positive integer"
  fi
  if ! [[ "$LIVE_SMOKE_POLL_INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || (( LIVE_SMOKE_POLL_INTERVAL_SECONDS <= 0 )); then
    fail "invalid --poll-interval-seconds=${LIVE_SMOKE_POLL_INTERVAL_SECONDS}; expected positive integer"
  fi
  if ! [[ "$LIVE_SMOKE_HEARTBEAT_SECONDS" =~ ^[0-9]+$ ]] || (( LIVE_SMOKE_HEARTBEAT_SECONDS <= 0 )); then
    fail "invalid --heartbeat-seconds=${LIVE_SMOKE_HEARTBEAT_SECONDS}; expected positive integer"
  fi
  if ! [[ "$LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS <= 0 )); then
    fail "invalid --external-probe-timeout-seconds=${LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS}; expected positive integer"
  fi
  if ! [[ "$LIVE_SMOKE_MAX_RETRIES" =~ ^[0-9]+$ ]] || (( LIVE_SMOKE_MAX_RETRIES <= 0 || LIVE_SMOKE_MAX_RETRIES > 2 )); then
    fail "invalid --max-retries=${LIVE_SMOKE_MAX_RETRIES}; expected integer in [1,2]"
  fi
  if [[ -z "$live_smoke_health_path" || "${live_smoke_health_path:0:1}" != "/" ]]; then
    fail "invalid --health-path=${live_smoke_health_path}; expected absolute path (e.g. /healthz)"
  fi

  local computer_use_strict
  computer_use_strict="$(printf '%s' "$LIVE_SMOKE_COMPUTER_USE_STRICT" | tr '[:upper:]' '[:lower:]')"
  require_enum "LIVE_SMOKE_COMPUTER_USE_STRICT" "$computer_use_strict" 0 1 true false yes no on off

  local computer_use_skip
  computer_use_skip="$(printf '%s' "$LIVE_SMOKE_COMPUTER_USE_SKIP" | tr '[:upper:]' '[:lower:]')"
  require_enum "LIVE_SMOKE_COMPUTER_USE_SKIP" "$computer_use_skip" 0 1 true false yes no on off

  local notification_lane_required
  notification_lane_required="$(printf '%s' "$LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE" | tr '[:upper:]' '[:lower:]')"
  require_enum "LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE" "$notification_lane_required" 0 1 true false yes no on off

  log "API target: base=${API_BASE_URL}"
  if [[ -z "$(trim_whitespace "$LIVE_SMOKE_COMPUTER_USE_CMD")" ]]; then
    LIVE_SMOKE_COMPUTER_USE_CMD="$ROOT_DIR/scripts/ci/smoke_computer_use_local.sh"
  fi
  LIVE_SMOKE_COMPUTER_USE_CMD="$(resolve_local_script_path "$LIVE_SMOKE_COMPUTER_USE_CMD")"
  ensure_valid_youtube_api_key
  local missing_core=()
  local missing_notification=()
  [[ -z "${GEMINI_API_KEY:-}" ]] && missing_core+=("GEMINI_API_KEY")
  [[ -z "${YOUTUBE_API_KEY:-}" ]] && missing_core+=("YOUTUBE_API_KEY")
  [[ -z "${RESEND_API_KEY:-}" ]] && missing_notification+=("RESEND_API_KEY")
  [[ -z "${RESEND_FROM_EMAIL:-}" ]] && missing_notification+=("RESEND_FROM_EMAIL")

  if [[ "${#missing_core[@]}" -gt 0 ]]; then
    if is_truthy "$LIVE_SMOKE_REQUIRE_SECRETS"; then
      fail "missing required core secrets: ${missing_core[*]}"
    fi
    log "SKIP: missing core secrets: ${missing_core[*]}"
    exit 0
  fi

  if [[ "${#missing_notification[@]}" -gt 0 ]]; then
    NOTIFICATION_LANE_READY="0"
    NOTIFICATION_LANE_REASON="missing notification lane prerequisites: ${missing_notification[*]}"
    if is_truthy "$notification_lane_required"; then
      fail "${NOTIFICATION_LANE_REASON}"
    fi
    log "notification lane degraded: ${NOTIFICATION_LANE_REASON}"
    record_scenario "notification_lane_prerequisites" "skipped" "${NOTIFICATION_LANE_REASON}"
  fi

  local llm_input_mode
  llm_input_mode="$(printf '%s' "${PIPELINE_LLM_INPUT_MODE:-auto}" | tr '[:upper:]' '[:lower:]')"
  require_enum "PIPELINE_LLM_INPUT_MODE" "$llm_input_mode" auto text video_text frames_text

  local thinking_level
  thinking_level="$(printf '%s' "${GEMINI_THINKING_LEVEL:-high}" | tr '[:upper:]' '[:lower:]')"
  require_enum "GEMINI_THINKING_LEVEL" "$thinking_level" minimal low medium high
  log "LLM strategy: provider=gemini model=${GEMINI_MODEL:-gemini-3.1-pro-preview} fast_model=${GEMINI_FAST_MODEL:-gemini-3-flash-preview} thinking=${thinking_level} input_mode=${llm_input_mode} cache=${GEMINI_CONTEXT_CACHE_ENABLED:-true}"

  local status body response
  response="$(api_get "$live_smoke_health_path")"
  status="${response%%$'\n'*}"
  body="${response#*$'\n'}"
  if [[ "$status" != "200" ]]; then
    if is_truthy "$LIVE_SMOKE_REQUIRE_API"; then
      fail "API health check failed: status=${status} body=${body}"
    fi
    log "SKIP: API is unavailable at ${API_BASE_URL} (status=${status})"
    exit 0
  fi

  record_scenario "api_healthz" "passed" "status=${status}"
}

probe_external_dependencies() {
  local gemini_status youtube_status bilibili_status probe_url
  local gemini_tmp youtube_tmp bilibili_tmp
  gemini_tmp="$(mktemp)"
  youtube_tmp="$(mktemp)"
  bilibili_tmp="$(mktemp)"
  SMOKE_TMP_FILES+=("$gemini_tmp" "$youtube_tmp" "$bilibili_tmp")

  probe_url="https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}"
  log "phase=short_tests step=external_probe_gemini"
  gemini_status="$(curl -sS -o "$gemini_tmp" -w '%{http_code}' --max-time "$LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS" \
    --retry "$((LIVE_SMOKE_MAX_RETRIES - 1))" --retry-delay 1 --retry-all-errors \
    "$probe_url")" || fail "external probe failed: gemini models endpoint unreachable"
  if [[ "$gemini_status" != "200" ]]; then
    fail "external probe failed: gemini models status=${gemini_status} body=$(head -c 300 "$gemini_tmp")"
  fi
  record_scenario "external_probe_gemini" "passed" "status=${gemini_status}"

  log "phase=short_tests step=external_probe_youtube_api"
  youtube_status="$(
    curl -sS -o "$youtube_tmp" -w '%{http_code}' --max-time "$LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS" \
      --retry "$((LIVE_SMOKE_MAX_RETRIES - 1))" --retry-delay 1 --retry-all-errors \
      "https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ&maxResults=1&key=${YOUTUBE_API_KEY}"
  )" || fail "external probe failed: youtube data api unreachable"
  if [[ "$youtube_status" != "200" ]]; then
    fail "external probe failed: youtube data api status=${youtube_status} body=$(head -c 300 "$youtube_tmp")"
  fi
  record_scenario "external_probe_youtube_api" "passed" "status=${youtube_status}"

  log "phase=short_tests step=external_probe_bilibili_web"
  bilibili_status="$(
    curl -sS -L -o "$bilibili_tmp" -w '%{http_code}' --max-time "$LIVE_SMOKE_EXTERNAL_PROBE_TIMEOUT_SECONDS" \
      --retry "$((LIVE_SMOKE_MAX_RETRIES - 1))" --retry-delay 1 --retry-all-errors \
      "$BILIBILI_SMOKE_URL"
  )" || fail "external probe failed: bilibili webpage unreachable"
  if [[ ! "$bilibili_status" =~ ^[23] ]]; then
    fail "external probe failed: bilibili webpage status=${bilibili_status}"
  fi
  record_scenario "external_probe_bilibili_web" "passed" "status=${bilibili_status}"
  rm -f "$gemini_tmp" "$youtube_tmp" "$bilibili_tmp"
}

run_external_browser_probe() {
  local cmd="$ROOT_DIR/scripts/ci/external_playwright_smoke.sh"
  [[ -x "$cmd" ]] || fail "external playwright smoke script missing or not executable: $cmd"
  log "phase=short_tests step=external_browser_real_probe"
  if "$cmd" \
    --url "https://example.com" \
    --browser "chromium" \
    --expect-text "Example Domain" \
    --timeout-ms "45000" \
    --retries "2" \
    --output-dir ".runtime-cache/evidence/tests/external-playwright-smoke" \
    --diagnostics-json ".runtime-cache/reports/tests/external-playwright-smoke-result.json"; then
    record_scenario "external_browser_real_probe" "passed" "url=https://example.com browser=chromium"
    return 0
  fi
  fail "external browser real probe failed"
}

run_computer_use_smoke() {
  local strict_value skip_value skip_reason cmd
  strict_value="$(printf '%s' "$LIVE_SMOKE_COMPUTER_USE_STRICT" | tr '[:upper:]' '[:lower:]')"
  skip_value="$(printf '%s' "$LIVE_SMOKE_COMPUTER_USE_SKIP" | tr '[:upper:]' '[:lower:]')"
  skip_reason="$(trim_whitespace "$LIVE_SMOKE_COMPUTER_USE_SKIP_REASON")"
  cmd="$(trim_whitespace "$LIVE_SMOKE_COMPUTER_USE_CMD")"

  if is_truthy "$skip_value"; then
    [[ -n "$skip_reason" ]] || fail "--computer-use-skip=1 requires --computer-use-skip-reason"
    log "Scenario: computer_use smoke skipped; reason=${skip_reason}"
    record_scenario "computer_use_smoke" "skipped" "$skip_reason"
    return 0
  fi

  if [[ -z "$cmd" ]]; then
    local message="computer_use smoke command is empty; set --computer-use-cmd or skip with --computer-use-skip=1 and --computer-use-skip-reason"
    if is_truthy "$strict_value"; then
      fail "$message"
    fi
    log "Scenario: computer_use smoke non-strict skip; reason=${message}"
    record_scenario "computer_use_smoke" "skipped" "$message"
    return 0
  fi

  log "Scenario: computer_use smoke"
  if "$cmd" \
    --api-base-url "$API_BASE_URL" \
    --retries "$LIVE_SMOKE_MAX_RETRIES" \
    --heartbeat-seconds "$LIVE_SMOKE_HEARTBEAT_SECONDS"; then
    log "computer_use smoke passed"
    record_scenario "computer_use_smoke" "passed" "cmd=${cmd}"
    record_write_operation \
      "computer_use_smoke_script" \
      "computer-use:${API_BASE_URL}" \
      "delegated script handles safe teardown and keeps audit-friendly records" \
      "cmd=${cmd}"
    return 0
  fi

  if is_truthy "$strict_value"; then
    fail "computer_use smoke failed: cmd=${cmd}"
  fi
  log "Scenario: computer_use smoke non-strict skip; reason=command failed cmd=${cmd}"
  record_scenario "computer_use_smoke" "skipped" "command failed cmd=${cmd}"
}

process_video() {
  local platform="$1"
  local url="$2"
  local mode="$3"
  local label="$4"
  local idempotency_key
  idempotency_key="$(
    PLATFORM="$platform" URL="$url" MODE="$mode" python3 - <<'PY'
import hashlib
import os

raw = "|".join(
    (
        "video_process",
        os.environ["PLATFORM"],
        os.environ["URL"],
        os.environ["MODE"],
        "force=true",
    )
)
print(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24])
PY
  )"

  local payload
  payload="$(
    PLATFORM="$platform" URL="$url" MODE="$mode" python3 - <<'PY'
import json
import os
print(json.dumps({
  "video": {"platform": os.environ["PLATFORM"], "url": os.environ["URL"]},
  "mode": os.environ["MODE"],
  "overrides": {},
  "force": True,
}))
PY
  )"
  local status body response
  response="$(api_post "/api/v1/videos/process" "$payload")"
  status="${response%%$'\n'*}"
  body="${response#*$'\n'}"
  if [[ "$status" != "202" ]]; then
    fail "${label} failed: status=${status} body=${body}"
  fi
  local job_id
  job_id="$(BODY="$body" python3 - <<'PY'
import json, os
obj = json.loads(os.environ["BODY"])
print(obj.get("job_id") or "")
PY
  )"
  [[ -z "$job_id" ]] && fail "${label} missing job_id: body=${body}"
  log "${label}: queued job_id=${job_id}"
  record_scenario "${label}" "queued" "job_id=${job_id}"
  record_write_operation \
    "POST /api/v1/videos/process:${label}" \
    "$idempotency_key" \
    "no destructive cleanup; keep traceable job records for audit" \
    "force=true mode=${mode} platform=${platform} job_id=${job_id}"
  printf '%s\n' "$job_id"
}

run_cleanup_workflow_via_api() {
  local probe_root="$ROOT_DIR/.runtime-cache/tmp/e2e-live-smoke-cleanup"
  local workspace_dir="$probe_root/workspace"
  local cache_dir="$probe_root/cache"
  local media_file="$workspace_dir/job-cleanup/downloads/media.mp4"
  local frame_file="$workspace_dir/job-cleanup/frames/frame_001.jpg"
  local digest_file="$workspace_dir/job-cleanup/artifacts/digest.md"
  local cache_old_file="$cache_dir/stale-cache.bin"
  local cache_keep_file="$cache_dir/fresh-cache.bin"
  local idempotency_key
  local payload
  local response
  local status
  local body

  mkdir -p \
    "$(dirname "$media_file")" \
    "$(dirname "$frame_file")" \
    "$(dirname "$digest_file")" \
    "$cache_dir"
  printf 'video-bytes' >"$media_file"
  printf 'frame-bytes' >"$frame_file"
  printf 'keep-digest' >"$digest_file"
  printf 'stale-cache' >"$cache_old_file"
  printf 'fresh-cache' >"$cache_keep_file"

  CLEANUP_MEDIA_FILE="$media_file" \
  CLEANUP_FRAME_FILE="$frame_file" \
  CLEANUP_DIGEST_FILE="$digest_file" \
  CLEANUP_CACHE_OLD_FILE="$cache_old_file" \
  python3 - <<'PY'
import os
from datetime import datetime, timedelta, timezone

old_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).timestamp()
for env_name in (
    "CLEANUP_MEDIA_FILE",
    "CLEANUP_FRAME_FILE",
    "CLEANUP_DIGEST_FILE",
    "CLEANUP_CACHE_OLD_FILE",
):
    path = os.environ[env_name]
    os.utime(path, (old_ts, old_ts))
PY

  idempotency_key="$(
    WORKSPACE_DIR="$workspace_dir" CACHE_DIR="$cache_dir" python3 - <<'PY'
import hashlib
import os

raw = "|".join(("cleanup_workflow", os.environ["WORKSPACE_DIR"], os.environ["CACHE_DIR"]))
print(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24])
PY
  )"
  payload="$(
    WORKSPACE_DIR="$workspace_dir" CACHE_DIR="$cache_dir" python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "workflow": "cleanup",
            "run_once": True,
            "wait_for_result": True,
            "payload": {
                "workspace_dir": os.environ["WORKSPACE_DIR"],
                "cache_dir": os.environ["CACHE_DIR"],
                "older_than_hours": 1,
                "cache_older_than_hours": 1,
                "cache_max_size_mb": 1,
            },
        }
    )
)
PY
  )"

  response="$(api_post "/api/v1/workflows/run" "$payload")"
  status="${response%%$'\n'*}"
  body="${response#*$'\n'}"
  if [[ "$status" != "200" ]]; then
    fail "cleanup_workflow_api failed: status=${status} body=${body}"
  fi

  if ! \
    CLEANUP_RESPONSE_BODY="$body" \
    EXPECT_WORKSPACE_DIR="$workspace_dir" \
    EXPECT_CACHE_DIR="$cache_dir" \
    EXPECT_MEDIA_FILE="$media_file" \
    EXPECT_FRAME_FILE="$frame_file" \
    EXPECT_DIGEST_FILE="$digest_file" \
    EXPECT_CACHE_OLD_FILE="$cache_old_file" \
    EXPECT_CACHE_KEEP_FILE="$cache_keep_file" \
    python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["CLEANUP_RESPONSE_BODY"])
result = payload.get("result") or {}

assert payload["workflow"] == "cleanup"
assert payload["workflow_name"] == "CleanupWorkspaceWorkflow"
assert payload["status"] == "completed"
assert result.get("ok") is True
assert result.get("workspace_dir") == os.environ["EXPECT_WORKSPACE_DIR"]
assert result.get("cache_dir") == os.environ["EXPECT_CACHE_DIR"]
assert int(result.get("deleted_files", 0)) >= 2
assert int(result.get("cache_deleted_files_by_age", 0)) >= 1
assert not Path(os.environ["EXPECT_MEDIA_FILE"]).exists()
assert not Path(os.environ["EXPECT_FRAME_FILE"]).exists()
assert Path(os.environ["EXPECT_DIGEST_FILE"]).exists()
assert not Path(os.environ["EXPECT_CACHE_OLD_FILE"]).exists()
assert Path(os.environ["EXPECT_CACHE_KEEP_FILE"]).exists()
PY
  then
    fail "cleanup_workflow_api returned unexpected payload or filesystem state: body=${body}"
  fi

  record_scenario "cleanup_workflow_api" "passed" "status=completed"
  record_write_operation \
    "POST /api/v1/workflows/run:cleanup_workflow_api" \
    "$idempotency_key" \
    "cleanup workflow only deletes isolated smoke workspace/cache files" \
    "workspace_dir=${workspace_dir} cache_dir=${cache_dir}"
}

wait_for_terminal_status() {
  local job_id="$1"
  local label="$2"
  local deadline=$((SECONDS + LIVE_SMOKE_TIMEOUT_SECONDS))
  local status=""
  local pipeline_final_status=""
  local effective_final_status=""
  local error_message=""
  local next_heartbeat=$((SECONDS + LIVE_SMOKE_HEARTBEAT_SECONDS))

  while (( SECONDS < deadline )); do
    assert_ci_runtime_alive "$label" "$job_id"
    local response http_status body parsed
    response="$(api_get "/api/v1/jobs/${job_id}")"
    http_status="${response%%$'\n'*}"
    body="${response#*$'\n'}"
    [[ "$http_status" == "200" ]] || fail "${label}: query failed for job_id=${job_id}, status=${http_status}, body=${body}"

    parsed="$(
      BODY="$body" python3 - <<'PY'
import json
import os

obj = json.loads(os.environ["BODY"])
status = str(obj.get("status") or "")
pipeline_final_status = str(obj.get("pipeline_final_status") or "")
error_message = str(obj.get("error_message") or "")
print("\t".join((status, pipeline_final_status, error_message)))
PY
    )"
    status="${parsed%%$'\t'*}"
    parsed="${parsed#*$'\t'}"
    pipeline_final_status="${parsed%%$'\t'*}"
    error_message="${parsed#*$'\t'}"
    effective_final_status="$status"
    if [[ -n "$pipeline_final_status" ]]; then
      effective_final_status="$pipeline_final_status"
    fi

    if [[ "$status" != "queued" && "$status" != "running" ]]; then
      if [[ "$effective_final_status" == "failed" ]]; then
        fail "${label}: terminal status failed for job_id=${job_id}, status=${status}, pipeline_final_status=${pipeline_final_status:-null}, error=${error_message:-null}"
      fi
      log "${label}: terminal status reached for job_id=${job_id}, status=${status}, pipeline_final_status=${pipeline_final_status:-null}"
      record_scenario "$label" "passed" "job_id=${job_id} status=${status} pipeline_final_status=${pipeline_final_status:-null}"
      return 0
    fi

    if (( SECONDS >= next_heartbeat )); then
      assert_ci_runtime_alive "$label" "$job_id"
      log "heartbeat: ${label} waiting job_id=${job_id} status=${status} pipeline_final_status=${pipeline_final_status:-null}"
      record_scenario "$label" "running" "job_id=${job_id} status=${status} pipeline_final_status=${pipeline_final_status:-null}"
      next_heartbeat=$((SECONDS + LIVE_SMOKE_HEARTBEAT_SECONDS))
    fi
    sleep "$LIVE_SMOKE_POLL_INTERVAL_SECONDS"
  done

  fail "${label}: timeout waiting terminal status for job_id=${job_id}, last_status=${status:-unknown}, last_pipeline_final_status=${pipeline_final_status:-null}"
}

assert_ci_runtime_alive() {
  local label="$1"
  local job_id="$2"

  if [[ -n "${LIVE_SMOKE_API_PID:-}" ]] && ! kill -0 "${LIVE_SMOKE_API_PID}" >/dev/null 2>&1; then
    fail "${label}: live-smoke runtime check failed (api process exited), job_id=${job_id}, pid=${LIVE_SMOKE_API_PID}"
  fi
  if [[ -n "${LIVE_SMOKE_WORKER_PID:-}" ]] && ! kill -0 "${LIVE_SMOKE_WORKER_PID}" >/dev/null 2>&1; then
    fail "${label}: live-smoke runtime check failed (worker process exited), job_id=${job_id}, pid=${LIVE_SMOKE_WORKER_PID}"
  fi
  if [[ -n "${LIVE_SMOKE_TEMPORAL_PID:-}" ]] && ! kill -0 "${LIVE_SMOKE_TEMPORAL_PID}" >/dev/null 2>&1; then
    fail "${label}: live-smoke runtime check failed (temporal process exited), job_id=${job_id}, pid=${LIVE_SMOKE_TEMPORAL_PID}"
  fi
}

run_worker_workflow_once() {
  local command_name="$1"
  shift
  local output_path="/tmp/${SCRIPT_NAME}.${command_name}.json"
  local worker_exit=0
  local invocation_mode="run-once"
  local -a run_once_args=("--run-once")

  # These commands enqueue/schedule workflows and can hang in live-smoke when no long-lived worker is running.
  # For smoke we only need deterministic start/dedupe signals, so use start-only mode.
  if [[ "$command_name" == "start-notification-retry-workflow" || "$command_name" == "start-daily-workflow" || "$command_name" == "start-provider-canary-workflow" ]]; then
    invocation_mode="start-only"
    run_once_args=()
  fi
  local idempotency_key
  idempotency_key="$(
    COMMAND_NAME="$command_name" INVOCATION_MODE="$invocation_mode" EXTRA_ARGS="$*" python3 - <<'PY'
import hashlib
import os

raw = "|".join(
    (
        "worker_run_once",
        os.environ["COMMAND_NAME"],
        os.environ.get("INVOCATION_MODE", "run-once"),
        os.environ.get("EXTRA_ARGS", ""),
    )
)
print(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24])
PY
  )"
  record_write_operation \
    "worker.main ${command_name} (${invocation_mode})" \
    "$idempotency_key" \
    "remove temp output file during teardown" \
    "args=$* output=${output_path}"
  start_long_phase_heartbeat "worker.main ${command_name}"
  (
    cd "$ROOT_DIR/apps/worker"
    worker_module_cmd=("-m" "worker.main" "$command_name")
    if ((${#run_once_args[@]} > 0)); then
      worker_module_cmd+=("${run_once_args[@]}")
    fi
    if (($# > 0)); then
      worker_module_cmd+=("$@")
    fi
    if [[ "$invocation_mode" == "start-only" ]]; then
      # start-only commands return immediately and don't require timeout watchdog.
      # Avoid timeout+uv process wrapping here to reduce interpreter finalization flakiness.
      if command -v uv >/dev/null 2>&1; then
        PYTHONPATH="$ROOT_DIR/apps/worker:$ROOT_DIR:${PYTHONPATH:-}" \
          uv run python "${worker_module_cmd[@]}" >"$output_path"
      elif command -v python3 >/dev/null 2>&1; then
        PYTHONPATH="$ROOT_DIR/apps/worker:$ROOT_DIR:${PYTHONPATH:-}" \
          python3 "${worker_module_cmd[@]}" >"$output_path"
      else
        fail "python runtime not found for worker command: ${command_name}"
      fi
    elif command -v timeout >/dev/null 2>&1; then
      if command -v uv >/dev/null 2>&1; then
        timeout --signal=TERM "${LIVE_SMOKE_TIMEOUT_SECONDS}s" \
          env PYTHONPATH="$ROOT_DIR/apps/worker:$ROOT_DIR:${PYTHONPATH:-}" \
          uv run python "${worker_module_cmd[@]}" >"$output_path"
      else
        timeout --signal=TERM "${LIVE_SMOKE_TIMEOUT_SECONDS}s" \
          env PYTHONPATH="$ROOT_DIR/apps/worker:$ROOT_DIR:${PYTHONPATH:-}" \
          python3 "${worker_module_cmd[@]}" >"$output_path"
      fi
    elif command -v uv >/dev/null 2>&1; then
      PYTHONPATH="$ROOT_DIR/apps/worker:$ROOT_DIR:${PYTHONPATH:-}" \
        uv run python "${worker_module_cmd[@]}" >"$output_path"
    else
      PYTHONPATH="$ROOT_DIR/apps/worker:$ROOT_DIR:${PYTHONPATH:-}" \
        python3 "${worker_module_cmd[@]}" >"$output_path"
    fi
  )
  worker_exit=$?
  stop_long_phase_heartbeat
  if [[ "$worker_exit" -eq 124 ]]; then
    fail "worker command timed out after ${LIVE_SMOKE_TIMEOUT_SECONDS}s: ${command_name}"
  fi
  if [[ "$worker_exit" -ne 0 ]]; then
    fail "worker command failed (exit=${worker_exit}): ${command_name}"
  fi
  WORKER_TMP_OUTPUTS+=("$output_path")
}

main() {
  check_prerequisites
  log "Diagnostics output: $DIAGNOSTICS_PATH"
  log "phase=short_tests status=start"
  record_scenario "init" "passed" "api_base_url=${API_BASE_URL}"
  probe_external_dependencies
  run_external_browser_probe
  log "phase=short_tests status=passed"

  log "phase=long_tests status=start"
  log "Scenario: cleanup workflow API closure"
  run_cleanup_workflow_via_api

  log "Scenario: YouTube full"
  local youtube_job_id
  youtube_job_id="$(process_video "youtube" "$YOUTUBE_SMOKE_URL" "full" "youtube_full")"
  wait_for_terminal_status "$youtube_job_id" "video_process:youtube_full"

  log "Scenario: Bilibili full"
  local bilibili_job_id
  bilibili_job_id="$(process_video "bilibili" "$BILIBILI_SMOKE_URL" "full" "bilibili_full")"
  wait_for_terminal_status "$bilibili_job_id" "video_process:bilibili_full"

  log "Scenario: Gemini degrade(text_only fallback path)"
  local degrade_job_id
  degrade_job_id="$(process_video "youtube" "$YOUTUBE_SMOKE_URL" "text_only" "gemini_degrade")"
  wait_for_terminal_status "$degrade_job_id" "video_process:gemini_degrade"

  if is_truthy "$NOTIFICATION_LANE_READY"; then
    log "Scenario: video_digest retry recovery"
    run_worker_workflow_once "start-notification-retry-workflow" --retry-batch-limit 20

    log "Scenario: daily_digest dedupe"
    run_worker_workflow_once "start-daily-workflow"
    run_worker_workflow_once "start-daily-workflow"

    log "Scenario: provider canary"
    run_worker_workflow_once "start-provider-canary-workflow" --timeout-seconds "$LIVE_SMOKE_TIMEOUT_SECONDS"
  else
    record_scenario "video_digest_retry_recovery" "skipped" "$NOTIFICATION_LANE_REASON"
    record_scenario "daily_digest_dedupe" "skipped" "$NOTIFICATION_LANE_REASON"
    record_scenario "provider_canary" "skipped" "$NOTIFICATION_LANE_REASON"
  fi

  run_computer_use_smoke
  log "phase=long_tests status=passed"
  run_teardown
  write_diagnostics "passed" ""
  log "LIVE SMOKE DONE failure_kind=none diagnostics_path=${DIAGNOSTICS_PATH}"
}

main "$@"
