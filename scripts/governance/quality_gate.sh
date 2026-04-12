#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_NAME="quality_gate"
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$ROOT_DIR/.runtime-cache/tmp/pycache}"

# Keep uv-managed environments out of the repo root so governance gates do not race with
# transient `.venv` creation during parallel checks.
# shellcheck source=./scripts/lib/standard_env.sh
source "$ROOT_DIR/scripts/lib/standard_env.sh"
ensure_external_uv_project_environment "$ROOT_DIR"

# shellcheck source=./scripts/runtime/logging.sh
source "$ROOT_DIR/scripts/runtime/logging.sh"
MODE="pre-push"
HEARTBEAT_SECONDS="25"
MUTATION_MIN_SCORE="0.64"
MUTATION_MIN_EFFECTIVE_RATIO="0.27"
MUTATION_MAX_NO_TESTS_RATIO="0.72"
PROFILE_ONLY="0"
FINAL_CHECK="0"
FINAL_SKIP_PREPUSH="0"
CHANGED_BACKEND_INPUT="auto"
CHANGED_WEB_INPUT="auto"
CHANGED_DEPS_INPUT="auto"
CHANGED_MIGRATIONS_INPUT="auto"
CI_DEDUPE="0"
SKIP_MUTATION="0"
STRICT_FULL_RUN="0"
CONTAINERIZED="auto"
CHANGED_BACKEND="true"
CHANGED_WEB="true"
CHANGED_DEPS="true"
CHANGED_MIGRATIONS="true"
EFFECTIVE_BACKEND_CHANGED="true"
EFFECTIVE_WEB_CHANGED="true"
WEB_DEP_MANIFEST_CHANGED="true"
CHANGED_DETECTION_SOURCE="manual"
CHANGED_DETECTION_RELIABLE="1"
CHANGED_FILE_LIST=""
DIFF_BASE_SOURCE="manual"
DIFF_BASE_SHA=""
PROFILES=()

qg_log() {
  local severity="$1"
  local event="$2"
  shift 2
  local message="$*"
  printf '[quality-gate] %s\n' "$message" >&2
  sourceharbor_log_json_only "$severity" "$event" "$message"
}

prepare_web_runtime() {
  if [[ -n "${WEB_RUNTIME_WEB_DIR:-}" && -x "${WEB_RUNTIME_WEB_DIR}/node_modules/.bin/next" ]]; then
    export WEB_RUNTIME_WEB_DIR
    return 0
  fi
  eval "$(bash "$ROOT_DIR/scripts/ci/prepare_web_runtime.sh" --shell-exports)"
  export WEB_RUNTIME_WEB_DIR
  export SOURCE_HARBOR_REPO_ROOT
}

prepare_python_coverage_report() {
  local coverage_dir="$ROOT_DIR/.runtime-cache/reports/python"
  local combined_file="$coverage_dir/.coverage"
  local coverage_candidates=()
  if [[ ! -d "$coverage_dir" ]]; then
    return 0
  fi

  if [[ -f "$combined_file" ]]; then
    return 0
  fi

  while IFS= read -r coverage_candidate; do
    coverage_candidates+=("$coverage_candidate")
  done < <(find "$coverage_dir" -maxdepth 1 -type f -name '.coverage.*' ! -name '*.meta.json' -print)

  if ((${#coverage_candidates[@]} == 0)); then
    return 0
  fi

  PYTHONDONTWRITEBYTECODE=1 uv run coverage combine --keep "${coverage_candidates[@]}" >/dev/null
}

usage() {
  cat <<'USAGE'
Usage:
  scripts/quality_gate.sh [--mode pre-commit|pre-push] [--heartbeat-seconds N] [--mutation-min-score N] [--profile NAME ...] [--profile-only] \
    [--changed-backend true|false|auto] [--changed-web true|false|auto] [--changed-deps true|false|auto] [--changed-migrations true|false|auto] [--ci-dedupe 0|1] [--skip-mutation 0|1] [--strict-full-run 0|1] \
    [--containerized 0|1|auto] [--mutation-min-effective-ratio N] [--mutation-max-no-tests-ratio N]
  scripts/quality_gate.sh --final-check [--skip-prepush] [--heartbeat-seconds N] [--mutation-min-score N]

Modes:
  pre-commit  Run fast local commit gate (parallel checks + staged doc drift).
  pre-push    Run short checks first, then long tests with heartbeat logs.
Profiles:
  local       Validate local profile governance.
  ci          Validate CI profile governance.
  live-smoke  Validate live-smoke profile governance.
Flags:
  --profile NAME   Append explicit profile checks (repeatable).
  --mutation-min-score N  Mutation score threshold (default: 0.64).
  --mutation-min-effective-ratio N  Mutation effective ratio threshold (default: 0.27).
  --mutation-max-no-tests-ratio N  Mutation no-tests ratio upper bound (default: 0.72).
  --profile-only   Run profile checks only, skip other quality gates.
  --changed-backend true|false|auto    Backend change hint (default: auto).
  --changed-web true|false|auto        Frontend change hint (default: auto).
  --changed-deps true|false|auto       Dependency change hint (default: auto).
  --changed-migrations true|false|auto Migration change hint (default: auto).
  --ci-dedupe 0|1  Pre-push only: when 1, skip checks covered by standalone CI jobs.
  --skip-mutation 0|1  Pre-push only: when 1, skip local mutation gate (CI remains source of truth).
  --strict-full-run 0|1  Force full pre-push gates regardless of change detection, disallow mutation skip, disable ci-dedupe, and require local real Postgres smoke.
  --final-check    Shortcut to run scripts/env/final_governance_check.sh.
  --skip-prepush   Used with --final-check to skip final pre-push phase.

Quality policy (blocking):
  - Lint errors must be zero (frontend + backend full lint).
  - Placebo assertions are forbidden.
  - Documentation drift gate is mandatory.
  - Secrets leak scan is mandatory.
  - Coverage thresholds: total >= 95%, core modules >= 95%. Python total >= 95%, Python core modules >= 95%, Web lines/functions >= 95% with Web branch floor enforced by Vitest (90%).
  - Mutation testing (Python core): mutation score >= configured threshold (default: 0.64).
USAGE
}

while (($# > 0)); do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --heartbeat-seconds)
      HEARTBEAT_SECONDS="${2:-}"
      shift 2
      ;;
    --mutation-min-score)
      MUTATION_MIN_SCORE="${2:-}"
      shift 2
      ;;
    --mutation-min-effective-ratio)
      MUTATION_MIN_EFFECTIVE_RATIO="${2:-}"
      shift 2
      ;;
    --mutation-max-no-tests-ratio)
      MUTATION_MAX_NO_TESTS_RATIO="${2:-}"
      shift 2
      ;;
    --profile)
      PROFILES+=("${2:-}")
      shift 2
      ;;
    --profile-only)
      PROFILE_ONLY="1"
      shift
      ;;
    --changed-backend)
      CHANGED_BACKEND_INPUT="${2:-}"
      shift 2
      ;;
    --changed-web)
      CHANGED_WEB_INPUT="${2:-}"
      shift 2
      ;;
    --changed-deps)
      CHANGED_DEPS_INPUT="${2:-}"
      shift 2
      ;;
    --changed-migrations)
      CHANGED_MIGRATIONS_INPUT="${2:-}"
      shift 2
      ;;
    --ci-dedupe)
      CI_DEDUPE="${2:-}"
      shift 2
      ;;
    --skip-mutation)
      SKIP_MUTATION="${2:-}"
      shift 2
      ;;
    --strict-full-run)
      STRICT_FULL_RUN="${2:-}"
      shift 2
      ;;
    --containerized)
      CONTAINERIZED="${2:-}"
      shift 2
      ;;
    --final-check)
      FINAL_CHECK="1"
      shift
      ;;
    --skip-prepush)
      FINAL_SKIP_PREPUSH="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[quality-gate] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" != "pre-commit" && "$MODE" != "pre-push" ]]; then
  echo "[quality-gate] invalid --mode: $MODE (expected pre-commit or pre-push)" >&2
  exit 2
fi

if ! [[ "$HEARTBEAT_SECONDS" =~ ^[0-9]+$ ]] || ((HEARTBEAT_SECONDS < 5)); then
  echo "[quality-gate] invalid --heartbeat-seconds: $HEARTBEAT_SECONDS" >&2
  exit 2
fi

if ! [[ "$MUTATION_MIN_SCORE" =~ ^0(\.[0-9]+)?$|^1(\.0+)?$ ]]; then
  echo "[quality-gate] invalid --mutation-min-score: $MUTATION_MIN_SCORE (expected 0.0..1.0)" >&2
  exit 2
fi

if ! [[ "$MUTATION_MIN_EFFECTIVE_RATIO" =~ ^0(\.[0-9]+)?$|^1(\.0+)?$ ]]; then
  echo "[quality-gate] invalid --mutation-min-effective-ratio: $MUTATION_MIN_EFFECTIVE_RATIO (expected 0.0..1.0)" >&2
  exit 2
fi

if ! [[ "$MUTATION_MAX_NO_TESTS_RATIO" =~ ^0(\.[0-9]+)?$|^1(\.0+)?$ ]]; then
  echo "[quality-gate] invalid --mutation-max-no-tests-ratio: $MUTATION_MAX_NO_TESTS_RATIO (expected 0.0..1.0)" >&2
  exit 2
fi

if [[ "$PROFILE_ONLY" != "0" && "$PROFILE_ONLY" != "1" ]]; then
  echo "[quality-gate] invalid --profile-only: $PROFILE_ONLY (expected flag)" >&2
  exit 2
fi

for tristate_arg in \
  "$CHANGED_BACKEND_INPUT" \
  "$CHANGED_WEB_INPUT" \
  "$CHANGED_DEPS_INPUT" \
  "$CHANGED_MIGRATIONS_INPUT"; do
  if [[ "$tristate_arg" != "true" && "$tristate_arg" != "false" && "$tristate_arg" != "auto" ]]; then
    echo "[quality-gate] invalid changed flag: ${tristate_arg} (expected true|false|auto)" >&2
    exit 2
  fi
done

if [[ "$CI_DEDUPE" != "0" && "$CI_DEDUPE" != "1" ]]; then
  echo "[quality-gate] invalid --ci-dedupe: $CI_DEDUPE (expected 0|1)" >&2
  exit 2
fi

if [[ "$SKIP_MUTATION" != "0" && "$SKIP_MUTATION" != "1" ]]; then
  echo "[quality-gate] invalid --skip-mutation: $SKIP_MUTATION (expected 0|1)" >&2
  exit 2
fi

if [[ "$STRICT_FULL_RUN" != "0" && "$STRICT_FULL_RUN" != "1" ]]; then
  echo "[quality-gate] invalid --strict-full-run: $STRICT_FULL_RUN (expected 0|1)" >&2
  exit 2
fi

if [[ "$CONTAINERIZED" != "0" && "$CONTAINERIZED" != "1" && "$CONTAINERIZED" != "auto" ]]; then
  echo "[quality-gate] invalid --containerized: $CONTAINERIZED (expected 0|1|auto)" >&2
  exit 2
fi

if [[ "$FINAL_SKIP_PREPUSH" == "1" && "$FINAL_CHECK" != "1" ]]; then
  echo "[quality-gate] --skip-prepush can only be used with --final-check" >&2
  exit 2
fi

if [[ "$STRICT_FULL_RUN" == "1" && "$MODE" != "pre-push" ]]; then
  echo "[quality-gate] --strict-full-run is only valid with --mode pre-push" >&2
  exit 2
fi

if [[ "$STRICT_FULL_RUN" == "1" && "$CI_DEDUPE" == "1" ]]; then
  echo "[quality-gate] --strict-full-run forbids --ci-dedupe=1" >&2
  exit 2
fi

if [[ "$STRICT_FULL_RUN" == "1" && "$SKIP_MUTATION" == "1" ]]; then
  echo "[quality-gate] --strict-full-run forbids --skip-mutation=1" >&2
  exit 2
fi

if [[ "$FINAL_CHECK" == "1" ]]; then
  final_cmd=(
    bash
    "$ROOT_DIR/scripts/env/final_governance_check.sh"
    --heartbeat-seconds
    "$HEARTBEAT_SECONDS"
    --mutation-min-score
    "$MUTATION_MIN_SCORE"
  )
  if [[ "$FINAL_SKIP_PREPUSH" == "1" ]]; then
    final_cmd+=(--skip-prepush)
  fi
  exec "${final_cmd[@]}"
fi

if ((${#PROFILES[@]} == 0)); then
  if [[ "$MODE" == "pre-commit" ]]; then
    PROFILES=("local")
  else
    PROFILES=("ci" "live-smoke")
  fi
fi

for profile in "${PROFILES[@]}"; do
  if [[ "$profile" != "local" && "$profile" != "ci" && "$profile" != "live-smoke" ]]; then
    echo "[quality-gate] invalid --profile: $profile (expected local|ci|live-smoke)" >&2
    exit 2
  fi
done

TMP_DIR="$(mktemp -d)"
quality_gate_summary_dir="$ROOT_DIR/.runtime-cache/reports/governance/quality-gate"
quality_gate_summary_tsv="$TMP_DIR/quality-gate-summary.tsv"
quality_gate_summary_json="$quality_gate_summary_dir/summary.json"
quality_gate_summary_md="$quality_gate_summary_dir/summary.md"
root_dirtiness_snapshot="$TMP_DIR/root-before.json"
mkdir -p "$quality_gate_summary_dir"
sourceharbor_log_init "governance" "$SCRIPT_NAME" "$ROOT_DIR/.runtime-cache/logs/governance/quality-gate.jsonl"
: > "$quality_gate_summary_tsv"

cleanup_quality_gate_residue() {
  local status="${1:-$?}"
  cleanup_source_tree_runtime_residue
  write_quality_gate_summary "$status"
  rm -rf "$TMP_DIR"
  return "$status"
}

cleanup_source_tree_runtime_residue() {
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$ROOT_DIR/.runtime-cache/tmp/pycache}" \
    python3 "$ROOT_DIR/scripts/runtime/clean_source_runtime_residue.py" --apply >/dev/null 2>&1 || true
}

trap cleanup_quality_gate_residue EXIT

cleanup_mutation_artifacts() {
  rm -rf "$ROOT_DIR/mutants" "$ROOT_DIR/apps/worker/mutants"
}

capture_root_snapshot() {
  python3 "$ROOT_DIR/scripts/governance/check_root_dirtiness_after_tasks.py" --write-snapshot "$root_dirtiness_snapshot"
}

verify_root_snapshot() {
  python3 "$ROOT_DIR/scripts/governance/check_root_dirtiness_after_tasks.py" --compare-snapshot "$root_dirtiness_snapshot"
}

RUN_IDS=()
RUN_NAMES=()
RUN_PIDS=()
quality_gate_current_phase="init"

run_async_gate() {
  local gate_id="$1"
  local gate_name="$2"
  local gate_cmd="$3"
  local gate_log="$TMP_DIR/${gate_id}.log"

  qg_log info gate_start "start: $gate_name"
  (
    cd "$ROOT_DIR"
    eval "$gate_cmd"
  ) >"$gate_log" 2>&1 &

  RUN_IDS+=("$gate_id")
  RUN_NAMES+=("$gate_name")
  RUN_PIDS+=("$!")
}

record_gate_status() {
  local gate_id="$1"
  local gate_name="$2"
  local status="$3"
  local gate_log="${4:-}"
  if [[ -z "${quality_gate_summary_tsv:-}" ]]; then
    quality_gate_summary_tsv="$TMP_DIR/quality-gate-summary.tsv"
  fi
  mkdir -p "$(dirname "$quality_gate_summary_tsv")"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$quality_gate_current_phase" \
    "$gate_id" \
    "$gate_name" \
    "$status" \
    "$gate_log" >> "$quality_gate_summary_tsv"
}

write_quality_gate_summary() {
  local exit_status="${1:-0}"
  [[ -n "$quality_gate_summary_tsv" ]] || return 0
  mkdir -p "$quality_gate_summary_dir"
  python3 - <<'PY' "$quality_gate_summary_tsv" "$quality_gate_summary_json" "$quality_gate_summary_md" "$MODE" "$exit_status" "$quality_gate_current_phase" "$CHANGED_DETECTION_SOURCE" "$CHANGED_BACKEND" "$CHANGED_WEB" "$CHANGED_DEPS" "$CHANGED_MIGRATIONS" "$EFFECTIVE_BACKEND_CHANGED" "$EFFECTIVE_WEB_CHANGED"
import json
import sys
from pathlib import Path
import sys

root = Path.cwd()
if str(root / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(root / "scripts" / "governance"))

from common import write_json_artifact, write_text_artifact

(
    tsv_path,
    json_path,
    md_path,
    mode,
    exit_status,
    final_phase,
    changed_source,
    changed_backend,
    changed_web,
    changed_deps,
    changed_migrations,
    effective_backend,
    effective_web,
) = sys.argv[1:]

rows = []
tsv = Path(tsv_path)
if tsv.exists():
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        phase, gate_id, gate_name, status, gate_log = line.split("\t", 4)
        rows.append(
            {
                "phase": phase,
                "id": gate_id,
                "name": gate_name,
                "status": status,
                "log_path": gate_log or None,
            }
        )

payload = {
    "mode": mode,
    "exit_status": int(exit_status),
    "result": "passed" if exit_status == "0" else "failed",
    "final_phase": final_phase,
    "changed_detection_source": changed_source,
    "changed": {
        "backend": changed_backend == "true",
        "web": changed_web == "true",
        "deps": changed_deps == "true",
        "migrations": changed_migrations == "true",
        "effective_backend": effective_backend == "true",
        "effective_web": effective_web == "true",
    },
    "gates": rows,
}

write_json_artifact(
    Path(json_path),
    payload,
    source_entrypoint="scripts/governance/quality_gate.sh",
    verification_scope="quality-gate-summary",
    source_run_id="governance-quality-gate-summary",
    freshness_window_hours=24,
    extra={"report_kind": "quality-gate-summary-json"},
)

lines = [
    "# Quality Gate Summary",
    "",
    f"- mode: `{mode}`",
    f"- result: `{'passed' if exit_status == '0' else 'failed'}`",
    f"- final_phase: `{final_phase}`",
    f"- changed_source: `{changed_source}`",
    "",
    "| Phase | Gate | Status | Log |",
    "| --- | --- | --- | --- |",
]
for row in rows:
    log_path = row["log_path"] or ""
    lines.append(f"| `{row['phase']}` | `{row['name']}` | `{row['status']}` | `{log_path}` |")
write_text_artifact(
    Path(md_path),
    "\n".join(lines) + "\n",
    source_entrypoint="scripts/governance/quality_gate.sh",
    verification_scope="quality-gate-summary",
    source_run_id="governance-quality-gate-summary",
    freshness_window_hours=24,
    extra={"report_kind": "quality-gate-summary-markdown"},
)
PY
}

set_quality_gate_phase() {
  quality_gate_current_phase="$1"
  echo "[quality-gate] phase=$2"
}

reset_async_buffers() {
  RUN_IDS=()
  RUN_NAMES=()
  RUN_PIDS=()
}

run_secrets_scan() {
  local matches filtered
  matches="$(
    rg -n --hidden --no-ignore-vcs \
      --glob "!.git/**" \
      --glob "!node_modules/**" \
      --glob "!.venv/**" \
      --glob "!.runtime-cache/**" \
      --glob "!dist/**" \
      --glob "!build/**" \
      --glob "!coverage/**" \
      --glob "!.next/**" \
      -e 'sk-[A-Za-z0-9]{20,}' \
      -e 'ghp_[A-Za-z0-9]{20,}' \
      -e 'AKIA[0-9A-Z]{16}' \
      -e '-----BEGIN [A-Z ]*PRIVATE KEY-----' \
      . || true
  )"

  filtered="$(
    printf '%s\n' "$matches" | rg -v \
      -e 'ghp_12345678901234567890' \
      -e 'AKIAIOSFODNN7EXAMPLE' \
      -e 'sk-test' \
      -e 'sk-dummy' \
      -e 'sk-placeholder' || true
  )"

  if [[ -n "$filtered" ]]; then
    printf '%s\n' "$filtered" >&2
    echo "[quality-gate] secrets leak scan failed" >&2
    return 1
  fi

  echo "[quality-gate] secrets leak scan passed"
}

run_tracked_real_env_guard() {
  local tracked blocked path
  tracked="$(git ls-files | rg '(^|/)\.env($|\.)|(^|/)env/.*\.env$' || true)"

  if [[ -z "$tracked" ]]; then
    echo "[quality-gate] real .env tracking guard passed"
    return 0
  fi

  blocked=""
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    case "$path" in
      env/profiles/*.env|*.env.example|*.env.sample|*.env.template)
        continue
        ;;
      *)
        blocked+="${path}"$'\n'
        ;;
    esac
  done <<< "$tracked"

  if [[ -n "$blocked" ]]; then
    printf '%s' "$blocked" >&2
    echo "[quality-gate] real .env tracking guard failed" >&2
    return 1
  fi

  echo "[quality-gate] real .env tracking guard passed"
}

run_gitleaks_fast_scan() {
  local config_args=()

  if ! command -v gitleaks >/dev/null 2>&1; then
    echo "[quality-gate] gitleaks not found; install gitleaks to proceed" >&2
    return 1
  fi

  if [[ -f "$ROOT_DIR/.gitleaks.toml" ]]; then
    config_args=(--config "$ROOT_DIR/.gitleaks.toml")
  fi

  if gitleaks protect --help >/dev/null 2>&1; then
    gitleaks protect --staged --redact "${config_args[@]}"
  elif gitleaks git --help >/dev/null 2>&1; then
    gitleaks git --staged --redact "${config_args[@]}"
  else
    gitleaks detect --source "$ROOT_DIR" --no-git --redact "${config_args[@]}"
  fi

  echo "[quality-gate] gitleaks lightweight scan passed"
}

run_hollow_log_guard() {
  local matches
  matches="$(
    rg -n -i \
      --glob '*.py' \
      -e 'logger\.(debug|info|warning|error|exception)\(\s*f?["'"'"'](something went wrong|unexpected error|error occurred|unknown error)["'"'"']' \
      apps/api apps/worker || true
  )"

  if [[ -n "$matches" ]]; then
    printf '%s\n' "$matches" >&2
    echo "[quality-gate] hollow log message guard failed" >&2
    return 1
  fi

  echo "[quality-gate] hollow log message guard passed"
}

run_test_focus_marker_guard() {
  python3 scripts/governance/check_test_focus_markers.py
}

run_e2e_strictness_guard() {
  python3 scripts/governance/check_e2e_strictness.py
}

run_mutation_scope_guard() {
  python3 scripts/governance/check_mutation_scope.py
}

run_mutation_test_selection_guard() {
  python3 scripts/governance/check_mutation_test_selection.py
}

run_ci_workflow_strictness_guard() {
  python3 scripts/governance/check_ci_workflow_strictness.py
}

run_env_governance_report_non_blocking() {
  local mode_tag="$1"
  local out_dir="$ROOT_DIR/.runtime-cache/reports/governance"
  local json_out="$out_dir/env-governance-${mode_tag}.json"
  local md_out="$out_dir/env-governance-${mode_tag}.md"
  mkdir -p "$out_dir"

  if ! python3 scripts/governance/report_env_governance.py \
    --json-out "$json_out" \
    --md-out "$md_out"; then
    echo "[quality-gate] env governance report detected issues (non-blocking): ${json_out}" >&2
  else
    echo "[quality-gate] env governance report generated: ${json_out}"
  fi
}

print_mutation_target_set() {
  local pyproject_file="$ROOT_DIR/pyproject.toml"

  if [[ ! -f "$pyproject_file" ]]; then
    echo "[quality-gate] mutation target set unavailable: pyproject.toml not found" >&2
    return 1
  fi

  python3 - "$pyproject_file" <<'PY'
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

pyproject_path = Path(sys.argv[1])
data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
paths = data.get("tool", {}).get("mutmut", {}).get("paths_to_mutate", [])
if not paths:
    print("[quality-gate] mutation target set is empty")
    raise SystemExit(1)

grouped = defaultdict(list)
for path in paths:
    if "/worker/pipeline/" in path:
        grouped["worker-pipeline"].append(path)
    elif "/api/app/services/" in path:
        grouped["api-services"].append(path)
    elif "/api/app/routers/" in path:
        grouped["api-routes"].append(path)
    else:
        grouped["other"].append(path)

print(f"[quality-gate] mutation target set count={len(paths)}")
for key in ("worker-pipeline", "api-services", "api-routes", "other"):
    values = grouped.get(key, [])
    if not values:
        continue
    print(f"[quality-gate] mutation target group={key} count={len(values)}")
    for item in values:
        print(f"[quality-gate]   - {item}")
PY
}

run_mutation_gate() {
  local mutation_report_dir="$ROOT_DIR/.runtime-cache/reports/mutation"
  local stats_file="$mutation_report_dir/mutmut-cicd-stats.json"
  echo "[quality-gate] mutation gate threshold=${MUTATION_MIN_SCORE} effective_ratio>=${MUTATION_MIN_EFFECTIVE_RATIO} no_tests_ratio<=${MUTATION_MAX_NO_TESTS_RATIO}"
  if ! print_mutation_target_set; then
    echo "[quality-gate] mutation gate failed: unable to load target set from pyproject.toml." >&2
    return 1
  fi

  if ! command -v uv >/dev/null 2>&1; then
    echo "[quality-gate] mutation gate failed: uv is required to auto-install/run mutmut." >&2
    echo "[quality-gate] install hint: python -m pip install 'uv==0.10.7'" >&2
    return 1
  fi

  if python3 - <<'PY' "$ROOT_DIR" "$stats_file"; then
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
stats_path = Path(sys.argv[2])
meta_path = stats_path.with_name(f"{stats_path.name}.meta.json")

if not stats_path.is_file() or not meta_path.is_file():
    raise SystemExit(1)

stats = json.loads(stats_path.read_text(encoding="utf-8"))
meta = json.loads(meta_path.read_text(encoding="utf-8"))
current_head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

if str(meta.get("source_commit") or "").strip() != current_head:
    raise SystemExit(1)
if str(meta.get("source_entrypoint") or "").strip() != "scripts/ci/run_mutmut.sh":
    raise SystemExit(1)
if "mutmut_run_exit" not in stats:
    raise SystemExit(1)
if int(stats.get("total", 0)) <= 0:
    raise SystemExit(1)
PY
    echo "[quality-gate] mutation gate reusing fresh current-commit stats at $stats_file"
  else
    local mutmut_run_exit=0
    bash "$ROOT_DIR/scripts/ci/run_mutmut.sh" || mutmut_run_exit=$?
    if (( mutmut_run_exit != 0 )); then
      echo "[quality-gate] mutation gate note: mutmut run exited with ${mutmut_run_exit}; evaluating exported stats against repo thresholds." >&2
    fi
  fi

  if [[ ! -f "$stats_file" ]]; then
    echo "[quality-gate] mutation gate failed: stats file missing at $stats_file." >&2
    return 1
  fi

  if ! python3 "$ROOT_DIR/scripts/governance/check_mutation_stats.py" \
    "$stats_file" \
    "$MUTATION_MIN_SCORE" \
    "$MUTATION_MIN_EFFECTIVE_RATIO" \
    "$MUTATION_MAX_NO_TESTS_RATIO"; then
    return 1
  fi

  echo "[quality-gate] mutation gate passed"
}

run_api_cors_preflight_smoke() {
  DATABASE_URL='sqlite+pysqlite:///:memory:' \
  TEMPORAL_TARGET_HOST='127.0.0.1:7233' \
  TEMPORAL_NAMESPACE='default' \
  TEMPORAL_TASK_QUEUE='video-analysis' \
  SQLITE_STATE_PATH="$TMP_DIR/api-cors-preflight.sqlite3" \
  NOTIFICATION_ENABLED='0' \
  PYTHONPATH="$ROOT_DIR:$ROOT_DIR/apps/worker" \
    uv run python - <<'PY'
from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
response = client.options(
    "/api/v1/subscriptions/123e4567-e89b-12d3-a456-426614174000",
    headers={
        "Origin": "http://127.0.0.1:3000",
        "Access-Control-Request-Method": "DELETE",
        "Access-Control-Request-Headers": "content-type",
    },
)
if response.status_code not in (200, 204):
    raise SystemExit(
        f"api cors preflight smoke failed: status={response.status_code}, body={response.text}"
    )
print("api cors preflight smoke passed")
PY
}

run_contract_diff_local_gate() {
  local base_sha=""
  local contract_dir="$ROOT_DIR/.runtime-cache/tmp/contract-diff-local"
  local base_tree="$contract_dir/base-tree"
  local base_json="$contract_dir/contract-base.json"
  local head_json="$contract_dir/contract-head.json"
  local report_md="$contract_dir/contract-diff.md"
  local report_json="$contract_dir/contract-diff.json"

  mkdir -p "$contract_dir"
  rm -rf "$base_tree"

  if ! resolve_pre_push_diff_base; then
    echo "[quality-gate] contract diff local gate failed: unable to determine base sha (source=${DIFF_BASE_SOURCE})" >&2
    return 1
  fi
  base_sha="$DIFF_BASE_SHA"

  git worktree add --detach "$base_tree" "$base_sha" >/dev/null

  if ! PYTHONPATH="$ROOT_DIR:$ROOT_DIR/apps/worker" \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///:memory:}" \
    uv run python scripts/governance/export_api_contract.py --repo-root "$ROOT_DIR" --output "$head_json"; then
    git worktree remove --force "$base_tree" >/dev/null 2>&1 || true
    return 1
  fi
  if ! PYTHONPATH="$ROOT_DIR:$ROOT_DIR/apps/worker" \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///:memory:}" \
    uv run python scripts/governance/export_api_contract.py --repo-root "$base_tree" --output "$base_json"; then
    git worktree remove --force "$base_tree" >/dev/null 2>&1 || true
    return 1
  fi
  if ! uv run python scripts/governance/check_contract_diff.py \
    --base "$base_json" \
    --head "$head_json" \
    --report "$report_md" \
    --json-report "$report_json"; then
    git worktree remove --force "$base_tree" >/dev/null 2>&1 || true
    return 1
  fi

  git worktree remove --force "$base_tree" >/dev/null 2>&1 || true
  echo "[quality-gate] contract diff local gate passed"
}

run_docs_governance_gate() {
  python3 scripts/governance/check_docs_governance.py
  echo "[quality-gate] docs governance control-plane gate passed"

  python3 scripts/governance/check_public_entrypoint_references.py
  echo "[quality-gate] public entrypoint reference gate passed"

  python3 scripts/governance/check_public_sensitive_surface.py
  echo "[quality-gate] public sensitive surface gate passed"

  python3 scripts/governance/check_remote_security_alerts.py
  echo "[quality-gate] remote security alert gate passed"

  python3 scripts/governance/check_route_contract_alignment.py
  echo "[quality-gate] route contract alignment gate passed"

  python3 scripts/governance/migrate_local_private_ledgers.py >/dev/null
  python3 scripts/governance/check_local_private_ledger_migration.py
  echo "[quality-gate] local private ledger migration gate passed"

  python3 scripts/governance/check_external_lane_contract.py
  echo "[quality-gate] external lane contract gate passed"

  python3 scripts/governance/check_eval_assets.py
  echo "[quality-gate] eval asset gate passed"
}

run_ci_smoke_drift_advisory() {
  if bash scripts/check_ci_smoke_drift.sh; then
    echo "[quality-gate] ci smoke drift check passed"
    return 0
  fi
  echo "[quality-gate] advisory: ci smoke drift check failed (non-blocking)" >&2
  return 0
}

run_docs_env_canonical_guard() {
  if rg -n 'cp \.env\.local\.example \.env\.local|source \.env\.local|自动加载 `?\.env\.local' README.md docs/runbook-local.md; then
    echo "[quality-gate] docs env canonical guard failed" >&2
    return 1
  fi
  echo "[quality-gate] docs env canonical guard passed"
}

run_provider_residual_guard() {
  bash scripts/governance/guard_provider_residuals.sh .
  echo "[quality-gate] provider residual guard passed"
}

run_worker_line_limits_guard() {
  python3 scripts/governance/check_worker_line_limits.py
  echo "[quality-gate] worker line limits guard passed"
}

run_schema_parity_gate() {
  python3 - <<'PY'
import difflib
import json
from pathlib import Path

source_path = Path("apps/mcp/schemas/tools.json")
shared_path = Path("contracts/generated/jsonschema/mcp-tools.schema.json")

source = json.loads(source_path.read_text(encoding="utf-8"))
shared = json.loads(shared_path.read_text(encoding="utf-8"))

if source != shared:
    source_pretty = json.dumps(source, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    shared_pretty = json.dumps(shared, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    print("Schema parity check failed:")
    for line in difflib.unified_diff(
        source_pretty,
        shared_pretty,
        fromfile=str(source_path),
        tofile=str(shared_path),
        lineterm="",
    ):
        print(line)
    raise SystemExit(1)
print("Schema parity check passed.")
PY
  echo "[quality-gate] schema parity gate passed"
}

run_iac_compose_config_validation() {
  if command -v docker >/dev/null 2>&1; then
    local compose_cmd=()
    if docker compose version >/dev/null 2>&1; then
      compose_cmd=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
      compose_cmd=(docker-compose)
    fi
    if ((${#compose_cmd[@]} > 0)); then
      "${compose_cmd[@]}" -f infra/compose/core-services.compose.yml config -q
      if [[ -f infra/compose/miniflux-nextflux.compose.yml ]]; then
        "${compose_cmd[@]}" -f infra/compose/miniflux-nextflux.compose.yml config -q
      fi
      echo "[quality-gate] iac compose config validation passed"
      return 0
    fi
  fi

  uv run --with pyyaml python3 - <<'PY'
from pathlib import Path
import yaml

for rel in ("infra/compose/core-services.compose.yml", "infra/compose/miniflux-nextflux.compose.yml"):
    path = Path(rel)
    if not path.is_file():
        continue
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "services" not in data:
        raise SystemExit(f"compose validation failed: {rel} missing top-level services")
print("compose yaml fallback validation passed")
PY
  echo "[quality-gate] iac compose config validation passed (yaml fallback)"
}

run_web_design_token_guard_local() {
  local base_sha=""

  if resolve_pre_push_diff_base; then
    base_sha="$DIFF_BASE_SHA"
    python3 scripts/governance/check_design_tokens.py \
      --from-ref "$base_sha" \
      --to-ref HEAD \
      apps/web
  else
    python3 scripts/governance/check_design_tokens.py --all-lines apps/web
  fi
  echo "[quality-gate] web design token guard passed"
}

run_python_tests_with_coverage_and_skip_guard() {
  PYTHON_TESTS_XDIST_WORKERS="${PYTHON_TESTS_XDIST_WORKERS:-0}" \
    bash scripts/ci/python_tests.sh
}

run_api_real_smoke_local_gate() {
  local default_api_real_smoke_database_url="${API_REAL_SMOKE_DATABASE_URL:-}"
  local default_api_real_smoke_temporal_target_host="${API_REAL_SMOKE_TEMPORAL_TARGET_HOST:-}"
  if [[ -z "$default_api_real_smoke_database_url" ]]; then
    if [[ "${SOURCE_HARBOR_IN_STANDARD_ENV:-0}" == "1" ]]; then
      default_api_real_smoke_database_url="postgresql+psycopg://postgres:postgres@host.docker.internal:5432/postgres"
    else
      default_api_real_smoke_database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
    fi
  fi
  if [[ -z "$default_api_real_smoke_temporal_target_host" ]]; then
    if [[ "${SOURCE_HARBOR_IN_STANDARD_ENV:-0}" == "1" ]]; then
      default_api_real_smoke_temporal_target_host="host.docker.internal:7233"
    else
      default_api_real_smoke_temporal_target_host="127.0.0.1:7233"
    fi
  fi
  if [[ -z "${DATABASE_URL:-}" || "${DATABASE_URL}" == "sqlite+pysqlite:///:memory:" ]]; then
    export DATABASE_URL="$default_api_real_smoke_database_url"
  fi
  if [[ -z "${TEMPORAL_TARGET_HOST:-}" || "${TEMPORAL_TARGET_HOST}" == "127.0.0.1:7233" ]]; then
    export TEMPORAL_TARGET_HOST="$default_api_real_smoke_temporal_target_host"
  fi
  ./scripts/ci/api_real_smoke.sh --profile ci
}

run_web_button_coverage_gate() {
  local -a args=(
    python3
    scripts/governance/check_web_button_coverage.py
    --threshold 1.0
    --e2e-threshold 0.6
    --unit-threshold 0.93
  )
  local changed_source_count=0
  local relative_path=""

  if [[ -n "$CHANGED_FILE_LIST" ]]; then
    while IFS= read -r relative_path; do
      [[ -n "$relative_path" ]] || continue
      [[ "$relative_path" == apps/web/* ]] || continue
      [[ "$relative_path" == *.tsx ]] || continue
      [[ "$relative_path" == *"/__tests__/"* ]] && continue
      [[ "$relative_path" == *"/tests/e2e/"* ]] && continue
      args+=(--source-file "$relative_path")
      changed_source_count=$((changed_source_count + 1))
    done <<< "$CHANGED_FILE_LIST"
  fi

  if (( changed_source_count == 0 )); then
    echo "[quality-gate] web interactive coverage gate skipped: no changed interactive web sources"
    return 0
  fi

  "${args[@]}"
}

run_web_dependency_policy_gate() {
  node - <<'JS'
const fs = require("fs");
const path = "apps/web/package.json";
const pkg = JSON.parse(fs.readFileSync(path, "utf8"));
const sections = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"];
const violations = [];

for (const section of sections) {
  const deps = pkg[section] || {};
  for (const [name, version] of Object.entries(deps)) {
    const v = String(version).trim();
    if (v === "latest" || v === "*" || /^https?:/i.test(v) || /^git\+/i.test(v)) {
      violations.push(`${section}.${name}=${v}`);
    }
  }
}

if (violations.length) {
  console.error("Floating dependency versions are not allowed:");
  for (const item of violations) console.error(`- ${item}`);
  process.exit(1);
}
console.log("Web dependency policy gate passed");
JS
}

report_gate_failure() {
  local gate_name="$1"
  local gate_log="$2"

  qg_log error gate_fail "FAIL: $gate_name"
  echo "[quality-gate] ----- ${gate_name} log (tail -n 80) -----" >&2
  tail -n 80 "$gate_log" >&2 || true
  echo "[quality-gate] ----------------------------------------" >&2
}

ensure_parallel_batch() {
  local phase_name="$1"
  local batch_size="${#RUN_PIDS[@]}"
  if ((batch_size <= 0)); then
    qg_log info phase_skip "phase '${phase_name}' no async tasks; skip wait"
    return 0
  fi
  if ((batch_size == 1)); then
    qg_log info phase_single_async "phase '${phase_name}' single async task; run without parallel requirement"
    return 0
  fi
  qg_log info phase_parallel "phase '${phase_name}' parallel tasks=${batch_size}"
}

wait_async_gates() {
  local had_failure=0
  local idx gate_id gate_name gate_pid gate_log

  for idx in "${!RUN_PIDS[@]}"; do
    gate_id="${RUN_IDS[$idx]}"
    gate_name="${RUN_NAMES[$idx]}"
    gate_pid="${RUN_PIDS[$idx]}"
    gate_log="$TMP_DIR/${gate_id}.log"

    if ! wait "$gate_pid"; then
      had_failure=1
      record_gate_status "$gate_id" "$gate_name" "failed" "$gate_log"
      report_gate_failure "$gate_name" "$gate_log"
    else
      record_gate_status "$gate_id" "$gate_name" "passed" "$gate_log"
      qg_log info gate_pass "pass: $gate_name"
    fi
  done

  return "$had_failure"
}

wait_async_gates_with_heartbeat() {
  local had_failure=0
  local running_names
  local idx gate_id gate_name gate_pid gate_log gate_state

  while :; do
    running_names=""
    for idx in "${!RUN_PIDS[@]}"; do
      gate_pid="${RUN_PIDS[$idx]}"
      gate_name="${RUN_NAMES[$idx]}"
      gate_state="$(ps -o stat= -p "$gate_pid" 2>/dev/null | tr -d '[:space:]')"
      if [[ -n "$gate_state" && "$gate_state" != *Z* ]]; then
        if [[ -z "$running_names" ]]; then
          running_names="$gate_name"
        else
          running_names="$running_names, $gate_name"
        fi
      fi
    done

    if [[ -z "$running_names" ]]; then
      break
    fi

    qg_log info long_phase_heartbeat "[heartbeat] long phase running: $running_names"
    sleep "$HEARTBEAT_SECONDS"
  done

  for idx in "${!RUN_PIDS[@]}"; do
    gate_id="${RUN_IDS[$idx]}"
    gate_name="${RUN_NAMES[$idx]}"
    gate_pid="${RUN_PIDS[$idx]}"
    gate_log="$TMP_DIR/${gate_id}.log"

    if ! wait "$gate_pid"; then
      had_failure=1
      record_gate_status "$gate_id" "$gate_name" "failed" "$gate_log"
      report_gate_failure "$gate_name" "$gate_log"
    else
      record_gate_status "$gate_id" "$gate_name" "passed" "$gate_log"
      qg_log info gate_pass "pass: $gate_name"
    fi
  done

  return "$had_failure"
}

run_sync_gate_with_heartbeat() {
  local gate_id="$1"
  local gate_name="$2"
  local gate_cmd="$3"
  local gate_log="$TMP_DIR/${gate_id}.log"
  local gate_pid running=true

  qg_log info gate_start "start: $gate_name"
  (
    cd "$ROOT_DIR"
    eval "$gate_cmd"
  ) >"$gate_log" 2>&1 &
  gate_pid="$!"

  while $running; do
    if kill -0 "$gate_pid" >/dev/null 2>&1; then
      qg_log info gate_heartbeat "[heartbeat] running: $gate_name"
      sleep "$HEARTBEAT_SECONDS"
    else
      running=false
    fi
  done

  if ! wait "$gate_pid"; then
    record_gate_status "$gate_id" "$gate_name" "failed" "$gate_log"
    report_gate_failure "$gate_name" "$gate_log"
    return 1
  fi

  record_gate_status "$gate_id" "$gate_name" "passed" "$gate_log"
  qg_log info gate_pass "pass: $gate_name"
}

is_true() {
  [[ "$1" == "true" ]]
}

resolve_pre_push_diff_base() {
  local upstream_ref=""
  local merge_base=""
  local remote_head_ref=""
  local root_commit=""
  local head_sha=""
  local empty_tree_sha=""
  local candidate=""

  DIFF_BASE_SOURCE=""
  DIFF_BASE_SHA=""

  if upstream_ref="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
    merge_base="$(git merge-base HEAD '@{upstream}' 2>/dev/null || true)"
    if [[ -n "$merge_base" ]]; then
      DIFF_BASE_SOURCE="upstream:${upstream_ref}"
      DIFF_BASE_SHA="$merge_base"
      return 0
    fi
  fi

  remote_head_ref="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
  if [[ -n "$remote_head_ref" ]]; then
    merge_base="$(git merge-base HEAD "$remote_head_ref" 2>/dev/null || true)"
    if [[ -n "$merge_base" ]]; then
      DIFF_BASE_SOURCE="origin-head:${remote_head_ref}"
      DIFF_BASE_SHA="$merge_base"
      return 0
    fi
  fi

  for candidate in origin/main origin/master origin/trunk; do
    if git rev-parse --verify "$candidate" >/dev/null 2>&1; then
      merge_base="$(git merge-base HEAD "$candidate" 2>/dev/null || true)"
      if [[ -n "$merge_base" ]]; then
        DIFF_BASE_SOURCE="origin-default-candidate:${candidate}"
        DIFF_BASE_SHA="$merge_base"
        return 0
      fi
    fi
  done

  root_commit="$(git rev-list --max-parents=0 HEAD 2>/dev/null | head -n 1 || true)"
  if [[ -n "$root_commit" ]]; then
    head_sha="$(git rev-parse HEAD 2>/dev/null || true)"
    if [[ -n "$head_sha" && "$root_commit" == "$head_sha" ]]; then
      empty_tree_sha="$(git hash-object -t tree /dev/null)"
      DIFF_BASE_SOURCE="root-commit-empty-tree"
      DIFF_BASE_SHA="$empty_tree_sha"
      return 0
    fi
    DIFF_BASE_SOURCE="root-commit"
    DIFF_BASE_SHA="$root_commit"
    return 0
  fi

  DIFF_BASE_SOURCE="base-unavailable"
  return 1
}

detect_changed_files() {
  local changed_files=""
  local base_sha=""

  CHANGED_DETECTION_RELIABLE="1"

  if [[ "$MODE" == "pre-commit" ]]; then
    CHANGED_DETECTION_SOURCE="staged"
    if ! changed_files="$(git diff --name-only --cached 2>/dev/null)"; then
      CHANGED_DETECTION_RELIABLE="0"
      CHANGED_DETECTION_SOURCE="staged-unavailable"
    fi
  else
    if resolve_pre_push_diff_base; then
      base_sha="$DIFF_BASE_SHA"
      CHANGED_DETECTION_SOURCE="${DIFF_BASE_SOURCE} (${base_sha}..HEAD)"
      if ! changed_files="$(git diff --name-only "$base_sha" HEAD 2>/dev/null)"; then
        CHANGED_DETECTION_RELIABLE="0"
      fi
    else
      CHANGED_DETECTION_RELIABLE="0"
      CHANGED_DETECTION_SOURCE="$DIFF_BASE_SOURCE"
    fi
  fi

  if [[ "$CHANGED_DETECTION_RELIABLE" != "1" ]]; then
    CHANGED_FILE_LIST=""
    return
  fi

  CHANGED_FILE_LIST="$changed_files"
}

match_changed_files() {
  local pattern="$1"

  if [[ -z "$CHANGED_FILE_LIST" ]]; then
    return 1
  fi

  printf '%s\n' "$CHANGED_FILE_LIST" | rg -q "$pattern"
}

resolve_changed_flags() {
  local auto_fallback="false"

  detect_changed_files

  if [[ "$STRICT_FULL_RUN" == "1" ]]; then
    CHANGED_BACKEND="true"
    CHANGED_WEB="true"
    CHANGED_DEPS="true"
    CHANGED_MIGRATIONS="true"
    EFFECTIVE_BACKEND_CHANGED="true"
    EFFECTIVE_WEB_CHANGED="true"
    CHANGED_DETECTION_SOURCE="strict-full-run-override"
    CHANGED_DETECTION_RELIABLE="1"
    return
  fi

  if [[ "$CHANGED_DETECTION_RELIABLE" != "1" ]]; then
    auto_fallback="true"
    echo "[quality-gate] changed detection unavailable; conservative fallback=true for auto flags" >&2
  fi

  if [[ "$CHANGED_BACKEND_INPUT" == "auto" ]]; then
    if [[ "$auto_fallback" == "true" ]]; then
      CHANGED_BACKEND="true"
    elif match_changed_files '^(apps/(api|worker|mcp)/|scripts/|infra/sql/|infra/config/|infra/compose/)'; then
      CHANGED_BACKEND="true"
    else
      CHANGED_BACKEND="false"
    fi
  else
    CHANGED_BACKEND="$CHANGED_BACKEND_INPUT"
  fi

  if [[ "$CHANGED_WEB_INPUT" == "auto" ]]; then
    if [[ "$auto_fallback" == "true" ]]; then
      CHANGED_WEB="true"
    elif match_changed_files '^apps/web/'; then
      CHANGED_WEB="true"
    else
      CHANGED_WEB="false"
    fi
  else
    CHANGED_WEB="$CHANGED_WEB_INPUT"
  fi

  if [[ "$CHANGED_DEPS_INPUT" == "auto" ]]; then
    if [[ "$auto_fallback" == "true" ]]; then
      CHANGED_DEPS="true"
    elif match_changed_files '(^|/)(pyproject\.toml|uv\.lock|requirements(\.txt)?|poetry\.lock|Pipfile(\.lock)?|package\.json|package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|yarn\.lock)$'; then
      CHANGED_DEPS="true"
    else
      CHANGED_DEPS="false"
    fi
  else
    CHANGED_DEPS="$CHANGED_DEPS_INPUT"
  fi

  if [[ "$CHANGED_MIGRATIONS_INPUT" == "auto" ]]; then
    if [[ "$auto_fallback" == "true" ]]; then
      CHANGED_MIGRATIONS="true"
    elif match_changed_files '^infra/migrations/.*\.sql$'; then
      CHANGED_MIGRATIONS="true"
    else
      CHANGED_MIGRATIONS="false"
    fi
  else
    CHANGED_MIGRATIONS="$CHANGED_MIGRATIONS_INPUT"
  fi

  EFFECTIVE_BACKEND_CHANGED="false"
  if is_true "$CHANGED_BACKEND" || is_true "$CHANGED_DEPS" || is_true "$CHANGED_MIGRATIONS"; then
    EFFECTIVE_BACKEND_CHANGED="true"
  fi

  WEB_DEP_MANIFEST_CHANGED="false"
  if match_changed_files '^apps/web/(package\.json|package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|yarn\.lock)$'; then
    WEB_DEP_MANIFEST_CHANGED="true"
  fi

  EFFECTIVE_WEB_CHANGED="false"
  if is_true "$CHANGED_WEB" || is_true "$WEB_DEP_MANIFEST_CHANGED"; then
    EFFECTIVE_WEB_CHANGED="true"
  fi

  echo "[quality-gate] changed flags: backend=${CHANGED_BACKEND}, web=${CHANGED_WEB}, deps=${CHANGED_DEPS}, migrations=${CHANGED_MIGRATIONS} web_dep_manifests=${WEB_DEP_MANIFEST_CHANGED} effective_backend=${EFFECTIVE_BACKEND_CHANGED} effective_web=${EFFECTIVE_WEB_CHANGED} source=${CHANGED_DETECTION_SOURCE}"
}

run_profile_gate() {
  local profile_name="$1"

  echo "[quality-gate] profile gate start: ${profile_name}"

  case "$profile_name" in
    local)
      python3 - <<'PY'
import re
from pathlib import Path

script = Path("scripts/ci/e2e_live_smoke.sh").read_text(encoding="utf-8")

required = [
    "--profile, --env-profile <name>",
    'ENV_PROFILE="${ENV_PROFILE:-local}"',
    'load_repo_env "$ROOT_DIR" "$SCRIPT_NAME" "$ENV_PROFILE"',
]
missing = sorted(item for item in required if item not in script)
if missing:
    raise SystemExit("local profile gate failed: missing CLI profile bindings: " + ", ".join(missing))
print("local profile gate passed")
PY
      ;;
    ci)
      python3 - <<'PY'
import json
from pathlib import Path

contract = json.loads(Path("infra/config/env.contract.json").read_text(encoding="utf-8"))
variables = {item["name"]: item for item in contract.get("variables", [])}
required = {
    "DATABASE_URL",
    "TEMPORAL_TARGET_HOST",
    "TEMPORAL_NAMESPACE",
    "TEMPORAL_TASK_QUEUE",
    "SQLITE_PATH",
    "SQLITE_STATE_PATH",
    "PIPELINE_WORKSPACE_DIR",
    "PIPELINE_ARTIFACT_ROOT",
    "UI_AUDIT_GEMINI_ENABLED",
    "NOTIFICATION_ENABLED",
}
missing = sorted(name for name in required if name not in variables)
if missing:
    raise SystemExit("ci profile gate failed: missing env contract vars: " + ", ".join(missing))
print("ci profile gate passed")
PY
      ;;
    live-smoke)
      python3 - <<'PY'
import re
from pathlib import Path

script = Path("scripts/ci/e2e_live_smoke.sh").read_text(encoding="utf-8")

required = [
    "--api-base-url <url>",
    "--require-api <0|1>",
    "--require-secrets <0|1>",
    "--computer-use-strict <0|1>",
    "--computer-use-skip <0|1>",
    "--computer-use-skip-reason <text>",
    "--max-retries <n>",
]
missing = sorted(item for item in required if item not in script)
if missing:
    raise SystemExit("live-smoke profile gate failed: missing CLI options: " + ", ".join(missing))

defaults = {
    "LIVE_SMOKE_REQUIRE_API": "1",
    "LIVE_SMOKE_REQUIRE_SECRETS": "1",
    "LIVE_SMOKE_COMPUTER_USE_STRICT": "1",
    "LIVE_SMOKE_COMPUTER_USE_SKIP": "0",
    "LIVE_SMOKE_MAX_RETRIES": "2",
}
for name, expected in defaults.items():
    pattern = rf'^{name}="{re.escape(expected)}"$'
    if not re.search(pattern, script, re.MULTILINE):
        raise SystemExit(f"live-smoke profile gate failed: {name} default must be '{expected}'")
print("live-smoke profile gate passed")
PY
      run_ci_smoke_drift_advisory
      ;;
  esac

  echo "[quality-gate] profile gate passed: ${profile_name}"
}

run_profile_gates_parallel() {
  local phase_name="$1"
  local profile

  if ((${#PROFILES[@]} < 2)); then
    for profile in "${PROFILES[@]}"; do
      run_profile_gate "$profile"
    done
    return 0
  fi

  reset_async_buffers
  for profile in "${PROFILES[@]}"; do
    run_async_gate "profile_${profile//-/_}" "profile gate (${profile})" "run_profile_gate '${profile}'"
  done

  ensure_parallel_batch "$phase_name"
  if ! wait_async_gates; then
    echo "[quality-gate] profile gate phase failed: ${phase_name}" >&2
    exit 1
  fi
}

run_pre_commit_mode() {
  cleanup_mutation_artifacts
  capture_root_snapshot

  echo "[quality-gate] mode=pre-commit"
  set_quality_gate_phase "pre-commit/profile-gates" "profile-gates (parallel)"
  run_profile_gates_parallel "pre-commit/profile-gates"
  if [[ "$PROFILE_ONLY" == "1" ]]; then
    echo "[quality-gate] profile-only passed"
    exit 0
  fi
  quality_gate_current_phase="pre-commit/short-checks"
  reset_async_buffers

  run_async_gate "doc_drift_staged" "documentation drift gate (staged)" \
    "bash scripts/governance/ci_or_local_gate_doc_drift.sh --scope staged"
  run_async_gate "docs_governance_gate" "docs governance control-plane gate" \
    "run_docs_governance_gate"
  run_async_gate "env_contract" "env contract" \
    "python3 scripts/governance/check_env_contract.py --strict"
  run_async_gate "host_safety_contract" "host safety contract" \
    "python3 scripts/governance/check_host_safety_contract.py"
  run_async_gate "placebo" "placebo assertion guard" \
    "python3 scripts/governance/check_test_assertions.py --path ."
  run_async_gate "secrets_scan" "secrets leak scan" \
    "run_secrets_scan"
  run_async_gate "tracked_real_env_guard" "real .env tracking guard" \
    "run_tracked_real_env_guard"
  run_async_gate "gitleaks_fast_scan" "gitleaks lightweight scan (if installed)" \
    "run_gitleaks_fast_scan"
  run_async_gate "hollow_log_guard" "hollow log message guard" \
    "run_hollow_log_guard"
  run_async_gate "test_focus_marker_guard" "test focus/todo marker guard" \
    "run_test_focus_marker_guard"
  run_async_gate "e2e_strictness_guard" "e2e strictness guard" \
    "run_e2e_strictness_guard"
  run_async_gate "mutation_scope_guard" "mutation scope guard" \
    "run_mutation_scope_guard"
  run_async_gate "mutation_test_selection_guard" "mutation test selection guard" \
    "run_mutation_test_selection_guard"
  run_async_gate "ci_workflow_strictness_guard" "ci workflow strictness guard" \
    "run_ci_workflow_strictness_guard"
  run_async_gate "governance_gate" "terminal governance gate" \
    "bash scripts/governance_gate.sh --mode pre-commit"
  run_async_gate "structured_log_guard" "structured log critical-path guard" \
    "python3 scripts/governance/check_structured_logs.py"
  run_async_gate "iac_entrypoint_guard" "iac entrypoint guard" \
    "bash scripts/governance/check_iac_entrypoint.sh ."
  run_async_gate "schema_parity_gate" "schema parity gate (apps/mcp vs contracts)" \
    "run_schema_parity_gate"
  run_async_gate "env_budget_guard" "env budget guard" \
    "python3 scripts/governance/check_env_budget.py"
  run_async_gate "env_governance_report" "env governance report (non-blocking)" \
    "run_env_governance_report_non_blocking pre-commit"
  if is_true "$EFFECTIVE_WEB_CHANGED"; then
    prepare_web_runtime
    run_async_gate "web_lint" "frontend lint" \
      "cd \"$WEB_RUNTIME_WEB_DIR\" && SOURCE_HARBOR_REPO_ROOT=\"$ROOT_DIR\" npm run lint"
  else
      record_gate_status "web_lint" "frontend lint" "skipped" ""
      echo "[quality-gate] skip: frontend lint (effective_web_changed=false)"
  fi
  if is_true "$EFFECTIVE_BACKEND_CHANGED"; then
    run_async_gate "ruff_full" "backend lint (ruff full rules)" \
      "uv run --with ruff ruff check apps/api apps/worker apps/mcp"
  else
      record_gate_status "ruff_full" "backend lint (ruff full rules)" "skipped" ""
      echo "[quality-gate] skip: backend lint (effective_backend_changed=false)"
  fi

  ensure_parallel_batch "pre-commit/short-checks"

  if ! wait_async_gates; then
    echo "[quality-gate] pre-commit gate failed" >&2
    exit 1
  fi

  set_quality_gate_phase "pre-commit/root-dirtiness" "root-dirtiness (post checks)"
  cleanup_source_tree_runtime_residue
  if ! run_sync_gate_with_heartbeat "root_dirtiness" "root dirtiness gate" "verify_root_snapshot"; then
    echo "[quality-gate] pre-commit failed in root-dirtiness phase" >&2
    exit 1
  fi

  echo "[quality-gate] pre-commit gate passed"
}

run_pre_push_mode() {
  local mutation_relevant_changed="false"
  local run_web_coverage_threshold_after_tests="false"

  cleanup_mutation_artifacts
  capture_root_snapshot

  if is_true "$EFFECTIVE_WEB_CHANGED"; then
    prepare_web_runtime
  fi

  echo "[quality-gate] mode=pre-push"
  set_quality_gate_phase "pre-push/profile-gates" "profile-gates (parallel)"
  run_profile_gates_parallel "pre-push/profile-gates"
  if [[ "$PROFILE_ONLY" == "1" ]]; then
    echo "[quality-gate] profile-only passed"
    exit 0
  fi

  set_quality_gate_phase "pre-push/short-checks" "short-checks (parallel)"
  reset_async_buffers

  run_async_gate "env_contract" "env contract" \
    "python3 scripts/governance/check_env_contract.py --strict"
  run_async_gate "host_safety_contract" "host safety contract" \
    "python3 scripts/governance/check_host_safety_contract.py"
  run_async_gate "env_budget_guard" "env budget guard" \
    "python3 scripts/governance/check_env_budget.py"
  run_async_gate "env_governance_report" "env governance report (non-blocking)" \
    "run_env_governance_report_non_blocking pre-push"
  run_async_gate "doc_drift_push" "documentation drift gate (push range)" \
    "bash scripts/governance/ci_or_local_gate_doc_drift.sh --scope push"
  run_async_gate "docs_governance_gate" "docs governance control-plane gate" \
    "run_docs_governance_gate"
  run_async_gate "placebo" "placebo assertion guard" \
    "python3 scripts/governance/check_test_assertions.py --path ."
  run_async_gate "secrets_scan" "secrets leak scan" \
    "run_secrets_scan"
  run_async_gate "hollow_log_guard" "hollow log message guard" \
    "run_hollow_log_guard"
  run_async_gate "test_focus_marker_guard" "test focus/todo marker guard" \
    "run_test_focus_marker_guard"
  run_async_gate "e2e_strictness_guard" "e2e strictness guard" \
    "run_e2e_strictness_guard"
  run_async_gate "mutation_scope_guard" "mutation scope guard" \
    "run_mutation_scope_guard"
  run_async_gate "mutation_test_selection_guard" "mutation test selection guard" \
    "run_mutation_test_selection_guard"
  run_async_gate "ci_workflow_strictness_guard" "ci workflow strictness guard" \
    "run_ci_workflow_strictness_guard"
  run_async_gate "governance_gate" "terminal governance gate" \
    "bash scripts/governance_gate.sh --mode pre-push"
  run_async_gate "structured_log_guard" "structured log critical-path guard" \
    "python3 scripts/governance/check_structured_logs.py"
  run_async_gate "iac_entrypoint_guard" "iac entrypoint guard" \
    "bash scripts/governance/check_iac_entrypoint.sh ."
  run_async_gate "iac_compose_config_validation" "iac compose config validation" \
    "run_iac_compose_config_validation"
  run_async_gate "docs_env_canonical_guard" "docs env canonical guard" \
    "run_docs_env_canonical_guard"
  run_async_gate "provider_residual_guard" "provider residual guard" \
    "run_provider_residual_guard"
  run_async_gate "worker_line_limits_guard" "worker line limits guard" \
    "run_worker_line_limits_guard"
  run_async_gate "schema_parity_gate" "schema parity gate (apps/mcp vs contracts)" \
    "run_schema_parity_gate"
  if [[ "$CI_DEDUPE" == "1" ]]; then
    record_gate_status "web_lint" "frontend lint" "skipped" ""
    echo "[quality-gate] skip: frontend lint (--ci-dedupe=1)"
  elif is_true "$EFFECTIVE_WEB_CHANGED"; then
    run_async_gate "web_lint" "frontend lint" \
      "cd \"$WEB_RUNTIME_WEB_DIR\" && npm run lint"
  else
    record_gate_status "web_lint" "frontend lint" "skipped" ""
    echo "[quality-gate] skip: frontend lint (effective_web_changed=false)"
  fi
  if [[ "$CI_DEDUPE" == "1" ]]; then
    record_gate_status "ruff_full" "backend lint (ruff full rules)" "skipped" ""
    echo "[quality-gate] skip: backend lint (ruff) (--ci-dedupe=1)"
  elif is_true "$EFFECTIVE_BACKEND_CHANGED"; then
    run_async_gate "ruff_full" "backend lint (ruff full rules)" \
      "uv run --with ruff ruff check apps/api apps/worker apps/mcp"
  else
    record_gate_status "ruff_full" "backend lint (ruff full rules)" "skipped" ""
    echo "[quality-gate] skip: backend lint (effective_backend_changed=false)"
  fi

  ensure_parallel_batch "pre-push/short-checks"

  if ! wait_async_gates; then
    echo "[quality-gate] pre-push failed in short-checks phase" >&2
    exit 1
  fi

  set_quality_gate_phase "pre-push/long-tests" "long-tests (parallel + heartbeat=${HEARTBEAT_SECONDS}s)"
  reset_async_buffers

  if [[ "$CI_DEDUPE" == "1" ]]; then
    record_gate_status "web_unit_tests" "web unit tests" "skipped" ""
    record_gate_status "web_coverage_threshold" "web coverage threshold gate (lines/functions global>=95, core>=95; branches via Vitest>=90)" "skipped" ""
    echo "[quality-gate] skip: web unit tests (--ci-dedupe=1)"
    echo "[quality-gate] skip: web coverage threshold gate (--ci-dedupe=1, covered by CI web-test-build)"
  elif is_true "$EFFECTIVE_WEB_CHANGED"; then
    run_async_gate "web_unit_tests" "web unit tests" \
      "SOURCE_HARBOR_REPO_ROOT=\"$ROOT_DIR\" npm --prefix \"$WEB_RUNTIME_WEB_DIR\" run test:coverage"
    run_web_coverage_threshold_after_tests="true"
    run_async_gate "web_design_token_guard" "web design token guard (local diff)" \
      "run_web_design_token_guard_local"
    run_async_gate "web_build" "web build" \
      "SOURCE_HARBOR_REPO_ROOT=\"$ROOT_DIR\" npm --prefix \"$WEB_RUNTIME_WEB_DIR\" run build"
    run_async_gate "web_button_coverage" "web interactive coverage gate (combined=1.0 e2e=0.6 unit=0.93)" \
      "run_web_button_coverage_gate"
  else
    record_gate_status "web_unit_tests" "web unit tests" "skipped" ""
    record_gate_status "web_coverage_threshold" "web coverage threshold gate (lines/functions global>=95, core>=95; branches via Vitest>=90)" "skipped" ""
    echo "[quality-gate] skip: web unit tests (effective_web_changed=false)"
    echo "[quality-gate] skip: web coverage threshold gate (effective_web_changed=false)"
  fi
  if [[ "$CI_DEDUPE" == "1" ]]; then
    record_gate_status "python_tests_with_coverage" "python tests + total coverage gate (>=95%)" "skipped" ""
    echo "[quality-gate] skip: python tests + total coverage (--ci-dedupe=1)"
  elif is_true "$EFFECTIVE_BACKEND_CHANGED"; then
    run_async_gate "python_tests_with_coverage" "python tests + total coverage gate (>=95%)" \
      "run_python_tests_with_coverage_and_skip_guard"
    run_async_gate "api_cors_preflight_smoke" "api cors preflight smoke (OPTIONS DELETE)" \
      "run_api_cors_preflight_smoke"
    run_async_gate "contract_diff_local_gate" "contract diff local gate (base vs head)" \
      "run_contract_diff_local_gate"
  else
    record_gate_status "python_tests_with_coverage" "python tests + total coverage gate (>=95%)" "skipped" ""
    echo "[quality-gate] skip: python tests + total coverage (effective_backend_changed=false)"
  fi
  if is_true "$CHANGED_DEPS"; then
    run_async_gate "python_dependency_audit" "python dependency audit (pip-audit)" \
      "uv run --with pip-audit pip-audit --progress-spinner off"
  else
    record_gate_status "python_dependency_audit" "python dependency audit (pip-audit)" "skipped" ""
    echo "[quality-gate] skip: dependency vulnerability scan (changed_deps=false)"
  fi

  if is_true "$WEB_DEP_MANIFEST_CHANGED"; then
    run_async_gate "web_dependency_policy_gate" "web dependency policy gate (no floating versions)" \
      "run_web_dependency_policy_gate"
    run_async_gate "web_runtime_dependency_audit" "web runtime dependency audit (npm audit high+)" \
      "SOURCE_HARBOR_REPO_ROOT=\"$ROOT_DIR\" npm --prefix \"$WEB_RUNTIME_WEB_DIR\" audit --omit=dev --audit-level=high"
  else
    record_gate_status "web_dependency_policy_gate" "web dependency policy gate (no floating versions)" "skipped" ""
    record_gate_status "web_runtime_dependency_audit" "web runtime dependency audit (npm audit high+)" "skipped" ""
    echo "[quality-gate] skip: web dependency policy gate (web_dep_manifest_changed=false)"
    echo "[quality-gate] skip: web runtime dependency audit (web_dep_manifest_changed=false)"
  fi

  ensure_parallel_batch "pre-push/long-tests"

  if ! wait_async_gates_with_heartbeat; then
    echo "[quality-gate] pre-push failed in long-tests phase" >&2
    exit 1
  fi

  if [[ "$run_web_coverage_threshold_after_tests" == "true" ]]; then
    set_quality_gate_phase "pre-push/web-coverage-threshold" "web-coverage-threshold (post web unit tests)"
    if ! run_sync_gate_with_heartbeat "web_coverage_threshold" "web coverage threshold gate (lines/functions global>=95, core>=95; branches via Vitest>=90)" \
      "python3 scripts/governance/check_web_coverage_threshold.py --summary-path .runtime-cache/reports/web-coverage/coverage-summary.json --global-threshold 95 --core-threshold 95 --metric lines --metric functions"; then
      echo "[quality-gate] pre-push failed in web-coverage-threshold phase" >&2
      exit 1
    fi
  fi

  set_quality_gate_phase "pre-push/coverage-core-gates" "coverage-core-gates (parallel)"
  reset_async_buffers

  if [[ "$CI_DEDUPE" == "1" ]]; then
    record_gate_status "coverage_worker_core_95" "worker core coverage gate (>=95%)" "skipped" ""
    record_gate_status "coverage_api_core_95" "api core coverage gate (>=95%)" "skipped" ""
    echo "[quality-gate] skip: coverage core gates (--ci-dedupe=1)"
  elif is_true "$EFFECTIVE_BACKEND_CHANGED"; then
    prepare_python_coverage_report
    run_async_gate "coverage_worker_core_95" "worker core coverage gate (>=95%)" \
      "uv run coverage report --data-file=.runtime-cache/reports/python/.coverage --include=\"apps/worker/worker/pipeline/orchestrator.py,*/apps/worker/worker/pipeline/orchestrator.py,apps/worker/worker/pipeline/policies.py,*/apps/worker/worker/pipeline/policies.py,apps/worker/worker/pipeline/runner.py,*/apps/worker/worker/pipeline/runner.py,apps/worker/worker/pipeline/types.py,*/apps/worker/worker/pipeline/types.py\" --show-missing --fail-under=95"
    run_async_gate "coverage_api_core_95" "api core coverage gate (>=95%)" \
      "uv run coverage report --data-file=.runtime-cache/reports/python/.coverage --include=\"apps/api/app/routers/ingest.py,*/apps/api/app/routers/ingest.py,apps/api/app/routers/jobs.py,*/apps/api/app/routers/jobs.py,apps/api/app/routers/subscriptions.py,*/apps/api/app/routers/subscriptions.py,apps/api/app/routers/videos.py,*/apps/api/app/routers/videos.py,apps/api/app/services/jobs.py,*/apps/api/app/services/jobs.py,apps/api/app/services/subscriptions.py,*/apps/api/app/services/subscriptions.py,apps/api/app/services/videos.py,*/apps/api/app/services/videos.py\" --show-missing --fail-under=95"
  else
    record_gate_status "coverage_worker_core_95" "worker core coverage gate (>=95%)" "skipped" ""
    record_gate_status "coverage_api_core_95" "api core coverage gate (>=95%)" "skipped" ""
    echo "[quality-gate] skip: coverage core gates (effective_backend_changed=false)"
  fi

  ensure_parallel_batch "pre-push/coverage-core-gates"

  if ! wait_async_gates; then
    echo "[quality-gate] pre-push failed in coverage-core-gates phase" >&2
    exit 1
  fi

  if [[ "$STRICT_FULL_RUN" == "1" || "$CHANGED_DETECTION_RELIABLE" != "1" ]]; then
    mutation_relevant_changed="true"
  elif is_true "$EFFECTIVE_BACKEND_CHANGED"; then
    mutation_relevant_changed="true"
  elif match_changed_files '^(apps/(api|worker)/|pyproject\.toml$|uv\.lock$)'; then
    mutation_relevant_changed="true"
  fi

  if [[ "$SKIP_MUTATION" == "1" ]]; then
    echo "[quality-gate] skip: mutation gate (--skip-mutation=1)"
  elif [[ "$mutation_relevant_changed" == "true" ]]; then
    set_quality_gate_phase "pre-push/mutation-gate" "mutation-gate (heartbeat=${HEARTBEAT_SECONDS}s)"
    if ! run_sync_gate_with_heartbeat "mutation_gate" "mutation gate" "run_mutation_gate"; then
      echo "[quality-gate] pre-push failed in mutation-gate phase" >&2
      exit 1
    fi
  else
    record_gate_status "mutation_gate" "mutation gate" "skipped" ""
    echo "[quality-gate] skip: mutation gate (mutation_relevant_changed=false)"
  fi

  if [[ "$STRICT_FULL_RUN" == "1" || ( "$CI_DEDUPE" != "1" && "$EFFECTIVE_BACKEND_CHANGED" == "true" ) ]]; then
    if [[ "$STRICT_FULL_RUN" == "1" ]]; then
      set_quality_gate_phase "pre-push/api-real-smoke-local" "api-real-smoke-local (strict-full-run)"
    else
      set_quality_gate_phase "pre-push/api-real-smoke-local" "api-real-smoke-local (backend changed)"
    fi
    if ! run_sync_gate_with_heartbeat "api_real_smoke_local" "api real smoke local (postgresql+psycopg)" \
      "run_api_real_smoke_local_gate"; then
      echo "[quality-gate] pre-push failed in api-real-smoke-local phase" >&2
      exit 1
    fi
  else
    record_gate_status "api_real_smoke_local" "api real smoke local (postgresql+psycopg)" "skipped" ""
    echo "[quality-gate] skip: api-real-smoke-local (effective_backend_changed=false or --ci-dedupe=1)"
  fi

  set_quality_gate_phase "pre-push/root-dirtiness" "root-dirtiness (post checks)"
  cleanup_source_tree_runtime_residue
  if ! run_sync_gate_with_heartbeat "root_dirtiness" "root dirtiness gate" "verify_root_snapshot"; then
    echo "[quality-gate] pre-push failed in root-dirtiness phase" >&2
    exit 1
  fi

  echo "[quality-gate] all checks passed"
}

if [[ "$MODE" == "pre-commit" ]]; then
  resolve_changed_flags
  run_pre_commit_mode
else
  if [[ "$STRICT_FULL_RUN" == "1" ]]; then
    SKIP_MUTATION="0"
    CI_DEDUPE="0"
  fi
  resolve_changed_flags
  run_pre_push_mode
fi
