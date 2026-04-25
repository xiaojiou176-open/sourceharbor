#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

is_linux_arm64() {
  local kernel machine
  kernel="$(uname -s)"
  machine="$(uname -m)"
  [[ "$kernel" == "Linux" && ( "$machine" == "aarch64" || "$machine" == "arm64" ) ]]
}

is_sourced_script() {
  [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

configure_strict_ci_python_environment() {
  local platform_id env_root repo_hash env_dir
  platform_id="$(uname -s)-$(uname -m)"
  env_root="${TMPDIR:-/tmp}"
  repo_hash="$(
    python3 - "$ROOT_DIR" <<'PY'
import hashlib
import sys

print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest()[:12])
PY
  )"
  env_dir="${UV_PROJECT_ENVIRONMENT:-${env_root%/}/sourceharbor-strict-ci/${repo_hash}/${platform_id}}"
  export UV_PROJECT_ENVIRONMENT="$env_dir"
  export VIRTUAL_ENV="$env_dir"
  export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
  case ":$PATH:" in
    *":$env_dir/bin:"*) ;;
    *) export PATH="$env_dir/bin:$PATH" ;;
  esac
}

resolve_web_runtime_dir() {
  local shell_exports
  shell_exports="$(bash "$ROOT_DIR/scripts/ci/prepare_web_runtime.sh" --shell-exports --skip-install 1)"
  eval "$shell_exports"
  printf '%s\n' "${WEB_RUNTIME_WEB_DIR:-}"
}

web_node_modules_ready() {
  local web_runtime_dir
  web_runtime_dir="${WEB_RUNTIME_WEB_DIR:-$(resolve_web_runtime_dir)}"
  [[ -d "$web_runtime_dir/node_modules" ]] || return 1
  [[ -x "$web_runtime_dir/node_modules/.bin/eslint" ]] || return 1

  (
    cd "$web_runtime_dir"
    node <<'EOF'
const fs = require("fs");
const checks = [
  () => require.resolve("eslint/package.json"),
  () => require.resolve("eslint-visitor-keys/package.json"),
  () => require("eslint"),
  () => {
    if (process.platform === "linux" && process.arch === "arm64") {
      if (!fs.existsSync("node_modules/@rollup/rollup-linux-arm64-gnu/rollup.linux-arm64-gnu.node")) {
        throw new Error("missing @rollup/rollup-linux-arm64-gnu native binary");
      }
      if (!fs.existsSync("node_modules/lightningcss/lightningcss.linux-arm64-gnu.node")) {
        throw new Error("missing lightningcss linux arm64 native binary");
      }
    }
  },
];

for (const check of checks) {
  try {
    check();
  } catch (error) {
    process.stderr.write(`[bootstrap_strict_ci_runtime] invalid runtime web workspace node_modules: ${error.message}\n`);
    process.exit(1);
  }
}
EOF
  )
}

repair_linux_arm64_optional_native_web_packages() {
  if ! is_linux_arm64; then
    return 0
  fi

  local web_runtime_dir
  web_runtime_dir="${WEB_RUNTIME_WEB_DIR:-$(resolve_web_runtime_dir)}"
  local lightningcss_expected="$web_runtime_dir/node_modules/lightningcss/lightningcss.linux-arm64-gnu.node"
  local lightningcss_vendor="$web_runtime_dir/node_modules/lightningcss-linux-arm64-gnu/lightningcss.linux-arm64-gnu.node"

  if [[ ! -f "$lightningcss_expected" && -f "$lightningcss_vendor" ]]; then
    mkdir -p "$(dirname "$lightningcss_expected")"
    cp "$lightningcss_vendor" "$lightningcss_expected"
  fi
}

remove_web_node_modules_tree() {
  local web_runtime_dir
  web_runtime_dir="${WEB_RUNTIME_WEB_DIR:-$(resolve_web_runtime_dir)}"
  local target="$web_runtime_dir/node_modules"
  if [[ ! -e "$target" ]]; then
    return 0
  fi

  local stale_target="${web_runtime_dir}/.node_modules-stale-$$"
  rm -rf "$stale_target" 2>/dev/null || true
  if mv "$target" "$stale_target" 2>/dev/null; then
    target="$stale_target"
  fi

  chmod -R u+w "$target" 2>/dev/null || true
  python3 - <<'PY' "$target"
from pathlib import Path
import shutil
import sys

target = Path(sys.argv[1])
shutil.rmtree(target, ignore_errors=True)
if target.exists():
    raise SystemExit(f"failed to remove stale path: {target}")
PY
}

if [[ "${STRICT_CI_BOOTSTRAP_LOAD_HELPERS_ONLY:-0}" != "1" ]]; then
  mkdir -p .runtime-cache/run/strict-ci
  export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
  export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///:memory:}"
  export TEMPORAL_TARGET_HOST="${TEMPORAL_TARGET_HOST:-127.0.0.1:7233}"
  export TEMPORAL_NAMESPACE="${TEMPORAL_NAMESPACE:-default}"
  export TEMPORAL_TASK_QUEUE="${TEMPORAL_TASK_QUEUE:-sourceharbor-worker}"
  export SQLITE_STATE_PATH="${SQLITE_STATE_PATH:-/tmp/sourceharbor-strict-api.db}"
  export SQLITE_PATH="${SQLITE_PATH:-/tmp/sourceharbor-strict-worker.db}"
  configure_strict_ci_python_environment
  uv sync --frozen --extra dev --extra e2e

  platform_id="$(uname -s)-$(uname -m)"
  web_hash_file=".runtime-cache/run/strict-ci/web-${platform_id}.sha256"
  web_hash="$(
    {
      sha256sum apps/web/package-lock.json
      sha256sum apps/web/package.json
      printf '%s\n' "$platform_id"
    } | sha256sum | awk '{print $1}'
  )"
  existing_web_hash=""
  if [[ -f "$web_hash_file" ]]; then
    existing_web_hash="$(cat "$web_hash_file" 2>/dev/null || true)"
  fi

  repair_linux_arm64_optional_native_web_packages

  # Always refresh the repo-side web runtime workspace once. The prepare script
  # already hashes the full apps/web source tree, so it can cheaply no-op when
  # nothing changed while still invalidating stale copied sources when only app
  # code changed but package manifests did not.
  bash "$ROOT_DIR/scripts/ci/prepare_web_runtime.sh" >/dev/null
  repair_linux_arm64_optional_native_web_packages

  if ! web_node_modules_ready || [[ "$existing_web_hash" != "$web_hash" ]]; then
    bash "$ROOT_DIR/scripts/ci/prepare_web_runtime.sh" >/dev/null
    repair_linux_arm64_optional_native_web_packages
    if web_node_modules_ready; then
      printf '%s' "$web_hash" > "$web_hash_file"
    elif is_sourced_script && is_linux_arm64; then
      true
    else
      exit 1
    fi
  fi
fi
