#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_ROOT="$ROOT_DIR/.runtime-cache/tmp/web-runtime"
WORKSPACE_WEB_DIR="$RUNTIME_ROOT/workspace/apps/web"
WORKSPACE_SDK_DIR="$RUNTIME_ROOT/workspace/packages/sourceharbor-sdk"
STATE_DIR="$ROOT_DIR/.runtime-cache/run/web-runtime"
HASH_FILE="$STATE_DIR/package.sha256"
READY_FILE="$STATE_DIR/ready"
LOCK_DIR="$STATE_DIR/.prepare-lock"
STALE_LOCK_SECONDS="${PREPARE_WEB_RUNTIME_STALE_LOCK_SECONDS:-300}"
SHELL_EXPORTS="0"
SKIP_INSTALL="0"
PLATFORM_ID="$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m)"

usage() {
  cat <<'EOF'
Usage: scripts/ci/prepare_web_runtime.sh [--shell-exports] [--skip-install 0|1]

Creates a repo-side runtime workspace for apps/web under .runtime-cache/tmp/web-runtime
so repo-tracked source directories do not host machine dependency state.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --shell-exports)
      SHELL_EXPORTS="1"
      shift
      ;;
    --skip-install)
      SKIP_INSTALL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[prepare_web_runtime] unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$RUNTIME_ROOT" "$STATE_DIR"

PACKAGE_HASH="$(
  python3 - <<'PY' "$ROOT_DIR"
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

root = Path(sys.argv[1])
roots = [root / "apps" / "web"]
sdk_source_root = root / "packages" / "sourceharbor-sdk"
if sdk_source_root.exists():
    roots.append(sdk_source_root)
blocked_names = {
    "node_modules",
    ".next",
    "coverage",
    "out",
    "build",
    "tsconfig.tsbuildinfo",
    ".DS_Store",
    "*.tgz",
}

digest = hashlib.sha256()
for source_dir in roots:
    for path in sorted(source_dir.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if any(part in {"node_modules", ".next", "coverage", "out", "build", "tsconfig.tsbuildinfo", ".DS_Store"} for part in path.parts):
            continue
        if path.name.endswith(".tgz"):
            continue
        if any(part.startswith(".next-e2e-") for part in path.parts):
            continue
        if path.is_dir():
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
print(digest.hexdigest(), end="")
PY
)"
PACKAGE_HASH="${PACKAGE_HASH}-${PLATFORM_ID}"

expected_lightningcss_artifact() {
  case "$PLATFORM_ID" in
    darwin-arm64) printf '%s\n' "lightningcss-darwin-arm64/lightningcss.darwin-arm64.node" ;;
    darwin-x86_64) printf '%s\n' "lightningcss-darwin-x64/lightningcss.darwin-x64.node" ;;
    linux-aarch64|linux-arm64) printf '%s\n' "lightningcss-linux-arm64-gnu/lightningcss.linux-arm64-gnu.node" ;;
    linux-x86_64) printf '%s\n' "lightningcss-linux-x64-gnu/lightningcss.linux-x64-gnu.node" ;;
    *) printf '%s\n' "" ;;
  esac
}

runtime_native_deps_ready() {
  local expected
  expected="$(expected_lightningcss_artifact)"
  if [[ -z "$expected" ]]; then
    return 0
  fi
  [[ -f "$WORKSPACE_WEB_DIR/node_modules/$expected" ]]
}

acquire_lock() {
  local attempts=0
  while ! mkdir "$LOCK_DIR" >/dev/null 2>&1; do
    if [[ -f "$LOCK_DIR/pid" ]]; then
      local owner_pid
      owner_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
      if [[ -n "$owner_pid" ]] && ! kill -0 "$owner_pid" >/dev/null 2>&1; then
        rm -rf "$LOCK_DIR"
        continue
      fi
    else
      local lock_age
      lock_age="$(
        python3 - <<'PY' "$LOCK_DIR"
from __future__ import annotations

from pathlib import Path
import sys
import time

lock_dir = Path(sys.argv[1])
print(int(max(0, time.time() - lock_dir.stat().st_mtime)), end="")
PY
      )"
      if [[ -n "$lock_age" ]] && (( lock_age >= STALE_LOCK_SECONDS )); then
        rm -rf "$LOCK_DIR"
        continue
      fi
    fi
    attempts=$((attempts + 1))
    if (( attempts > 120 )); then
      echo "[prepare_web_runtime] timeout waiting for lock: $LOCK_DIR" >&2
      exit 1
    fi
    sleep 1
  done
  printf '%s\n' "$$" > "$LOCK_DIR/pid"
}

release_lock() {
  rm -rf "$LOCK_DIR"
}

workspace_ready() {
  [[ -f "$READY_FILE" ]] || return 1
  [[ -f "$HASH_FILE" ]] || return 1
  [[ -d "$WORKSPACE_WEB_DIR" ]] || return 1
  [[ "$(cat "$HASH_FILE" 2>/dev/null || true)" == "$PACKAGE_HASH" ]] || return 1
  [[ -f "$WORKSPACE_WEB_DIR/eslint.config.mjs" ]] || return 1
  [[ -f "$WORKSPACE_WEB_DIR/tsconfig.json" ]] || return 1
  if [[ "$SKIP_INSTALL" != "1" ]]; then
    [[ -x "$WORKSPACE_WEB_DIR/node_modules/.bin/next" ]] || return 1
    runtime_native_deps_ready || return 1
  fi
  return 0
}

acquire_lock
trap release_lock EXIT

if workspace_ready; then
  if [[ "$SHELL_EXPORTS" == "1" ]]; then
    printf 'export WEB_RUNTIME_ROOT=%q\n' "$RUNTIME_ROOT"
    printf 'export WEB_RUNTIME_WEB_DIR=%q\n' "$WORKSPACE_WEB_DIR"
    printf 'export WEB_RUNTIME_PACKAGE_HASH=%q\n' "$PACKAGE_HASH"
  else
    printf 'WEB_RUNTIME_ROOT=%s\n' "$RUNTIME_ROOT"
    printf 'WEB_RUNTIME_WEB_DIR=%s\n' "$WORKSPACE_WEB_DIR"
    printf 'WEB_RUNTIME_PACKAGE_HASH=%s\n' "$PACKAGE_HASH"
  fi
  exit 0
fi

python3 - <<'PY' "$ROOT_DIR"
import errno
from pathlib import Path
import shutil
import sys
import time

root = Path(sys.argv[1])
web_dir = root / "apps" / "web"


def handle_remove_error(_func, _path, exc_info):
    target = Path(_path)
    error = exc_info[1]
    if isinstance(error, FileNotFoundError):
        return
    if target.is_symlink():
        try:
            target.unlink()
        except FileNotFoundError:
            return
        return
    if isinstance(error, OSError) and error.errno == errno.ENOTEMPTY:
        time.sleep(0.05)
        return
    raise error


def robust_rmtree(target: Path) -> None:
    for attempt in range(5):
        if target.is_symlink():
            try:
                target.unlink()
            except FileNotFoundError:
                return
            return
        if not target.exists():
            return
        try:
            shutil.rmtree(target, ignore_errors=False, onerror=handle_remove_error)
        except FileNotFoundError:
            return
        except OSError as error:
            if error.errno != errno.ENOTEMPTY or attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))
            continue
        if not target.exists():
            return
        time.sleep(0.05 * (attempt + 1))
    if target.exists():
        raise OSError(errno.ENOTEMPTY, f"failed to remove directory cleanly: {target}")


for child in web_dir.iterdir():
    if child.name == "node_modules" or child.name == ".next" or child.name.startswith(".next-e2e-"):
        if child.is_dir():
            robust_rmtree(child)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass
PY

python3 - <<'PY' "$ROOT_DIR" "$WORKSPACE_WEB_DIR" "$WORKSPACE_SDK_DIR"
import errno
from pathlib import Path
import shutil
import sys
import time

root = Path(sys.argv[1])
source_dir = root / "apps" / "web"
target_dir = Path(sys.argv[2])
sdk_source_dir = root / "packages" / "sourceharbor-sdk"
sdk_target_dir = Path(sys.argv[3])
staging_dir = target_dir.parent / f"{target_dir.name}.staging"
sdk_staging_dir = sdk_target_dir.parent / f"{sdk_target_dir.name}.staging"


def handle_remove_error(_func, _path, exc_info):
    target = Path(_path)
    error = exc_info[1]
    if isinstance(error, FileNotFoundError):
        return
    if target.is_symlink():
        try:
            target.unlink()
        except FileNotFoundError:
            return
        return
    if isinstance(error, OSError) and error.errno == errno.ENOTEMPTY:
        time.sleep(0.05)
        return
    raise error


def robust_rmtree(target: Path) -> None:
    for attempt in range(5):
        if target.is_symlink():
            try:
                target.unlink()
            except FileNotFoundError:
                return
            return
        if not target.exists():
            return
        try:
            shutil.rmtree(target, ignore_errors=False, onerror=handle_remove_error)
        except FileNotFoundError:
            return
        except OSError as error:
            if error.errno != errno.ENOTEMPTY or attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))
            continue
        if not target.exists():
            return
        time.sleep(0.05 * (attempt + 1))
    if target.exists():
        raise OSError(errno.ENOTEMPTY, f"failed to remove directory cleanly: {target}")

def ignore(_path: str, names: list[str]) -> set[str]:
    blocked = {
        "node_modules",
        ".next",
        ".next-e2e-gw0",
        "coverage",
        "out",
        "build",
        "tsconfig.tsbuildinfo",
        ".DS_Store",
    }
    ignored = {name for name in names if name in blocked}
    ignored.update({name for name in names if name.endswith(".tgz")})
    ignored.update({name for name in names if name.startswith(".next-e2e-")})
    return ignored

if staging_dir.exists():
    robust_rmtree(staging_dir)
if sdk_staging_dir.exists():
    robust_rmtree(sdk_staging_dir)
target_dir.parent.mkdir(parents=True, exist_ok=True)
sdk_target_dir.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source_dir, staging_dir, ignore=ignore, copy_function=shutil.copy)
if sdk_source_dir.exists():
    shutil.copytree(sdk_source_dir, sdk_staging_dir, ignore=ignore, copy_function=shutil.copy)
if target_dir.exists():
    robust_rmtree(target_dir)
if sdk_target_dir.exists():
    robust_rmtree(sdk_target_dir)
staging_dir.rename(target_dir)
if sdk_staging_dir.exists():
    sdk_staging_dir.rename(sdk_target_dir)
PY

CURRENT_HASH=""
if [[ -f "$HASH_FILE" ]]; then
  CURRENT_HASH="$(cat "$HASH_FILE" 2>/dev/null || true)"
fi

if [[ "$SKIP_INSTALL" != "1" ]]; then
  if [[ ! -x "$WORKSPACE_WEB_DIR/node_modules/.bin/next" || "$CURRENT_HASH" != "$PACKAGE_HASH" ]]; then
    if [[ "$SHELL_EXPORTS" == "1" ]]; then
      (cd "$WORKSPACE_WEB_DIR" && npm ci --no-audit --no-fund) >&2
    else
      (cd "$WORKSPACE_WEB_DIR" && npm ci --no-audit --no-fund)
    fi
    printf '%s' "$PACKAGE_HASH" > "$HASH_FILE"
  fi
  if ! runtime_native_deps_ready; then
    rm -rf "$WORKSPACE_WEB_DIR/node_modules"
    if [[ "$SHELL_EXPORTS" == "1" ]]; then
      (cd "$WORKSPACE_WEB_DIR" && npm ci --no-audit --no-fund) >&2
    else
      (cd "$WORKSPACE_WEB_DIR" && npm ci --no-audit --no-fund)
    fi
    runtime_native_deps_ready || {
      echo "[prepare_web_runtime] expected native runtime dependency missing for platform $PLATFORM_ID" >&2
      exit 1
    }
  fi
fi

if [[ -d "$WORKSPACE_SDK_DIR" ]]; then
  if [[ "$SHELL_EXPORTS" == "1" ]]; then
    (cd "$WORKSPACE_SDK_DIR" && npm run build) >&2
  else
    (cd "$WORKSPACE_SDK_DIR" && npm run build)
  fi
fi

printf '%s\n' "$PACKAGE_HASH" > "$HASH_FILE"
printf 'ready\n' > "$READY_FILE"

if [[ "$SHELL_EXPORTS" == "1" ]]; then
  printf 'export WEB_RUNTIME_ROOT=%q\n' "$RUNTIME_ROOT"
  printf 'export WEB_RUNTIME_WEB_DIR=%q\n' "$WORKSPACE_WEB_DIR"
  printf 'export WEB_RUNTIME_PACKAGE_HASH=%q\n' "$PACKAGE_HASH"
  printf 'export SOURCE_HARBOR_REPO_ROOT=%q\n' "$ROOT_DIR"
else
  printf 'WEB_RUNTIME_ROOT=%s\n' "$RUNTIME_ROOT"
  printf 'WEB_RUNTIME_WEB_DIR=%s\n' "$WORKSPACE_WEB_DIR"
  printf 'WEB_RUNTIME_PACKAGE_HASH=%s\n' "$PACKAGE_HASH"
  printf 'SOURCE_HARBOR_REPO_ROOT=%s\n' "$ROOT_DIR"
fi
