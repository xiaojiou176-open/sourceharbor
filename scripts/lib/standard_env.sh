#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
eval "$(python3 "$ROOT_DIR/scripts/ci/contract.py" shell-exports)"
STANDARD_ENV_IMAGE="${SOURCE_HARBOR_STANDARD_ENV_IMAGE:-$STRICT_CI_STANDARD_IMAGE_REF}"
STANDARD_ENV_DOCKERFILE="${SOURCE_HARBOR_STANDARD_ENV_DOCKERFILE:-$ROOT_DIR/$STRICT_CI_STANDARD_IMAGE_DOCKERFILE}"
STANDARD_ENV_WORKDIR="${SOURCE_HARBOR_STANDARD_ENV_WORKDIR:-$STRICT_CI_STANDARD_IMAGE_WORKDIR}"
STANDARD_ENV_HOST_GATEWAY="${SOURCE_HARBOR_STANDARD_ENV_HOST_GATEWAY:-host.docker.internal}"
STANDARD_ENV_MARKER_PATH="${SOURCE_HARBOR_STANDARD_ENV_MARKER_PATH:-/etc/sourceharbor-strict-ci-standard-env}"
STANDARD_ENV_DOCKERENV_PATH="${SOURCE_HARBOR_STANDARD_ENV_DOCKERENV_PATH:-/.dockerenv}"
STANDARD_ENV_LOCAL_FALLBACK_ON_PULL_FAILURE="${SOURCE_HARBOR_STANDARD_ENV_LOCAL_FALLBACK_ON_PULL_FAILURE:-1}"

is_truthy_env() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

is_running_inside_standard_env() {
  if [[ "${SOURCE_HARBOR_IN_STANDARD_ENV:-0}" == "1" ]]; then
    return 0
  fi

  if [[ -f "$STANDARD_ENV_MARKER_PATH" ]]; then
    return 0
  fi

  # Legacy fallback: CI container jobs in GitHub Actions may run in the strict
  # image without propagating SOURCE_HARBOR_IN_STANDARD_ENV.
  if is_truthy_env "${GITHUB_ACTIONS:-}" && [[ -f "$STANDARD_ENV_DOCKERENV_PATH" ]]; then
    return 0
  fi

  return 1
}

append_standard_env_git_mounts() {
  local -n mounts_ref="$1"
  local git_file="$ROOT_DIR/.git"
  local git_dir=""
  local git_common_dir=""

  if [[ -d "$git_file" ]]; then
    return 0
  fi
  if [[ ! -f "$git_file" ]]; then
    return 0
  fi

  git_dir="$(git -C "$ROOT_DIR" rev-parse --absolute-git-dir 2>/dev/null || true)"
  git_common_dir="$(git -C "$ROOT_DIR" rev-parse --git-common-dir 2>/dev/null || true)"
  [[ -n "$git_dir" ]] || return 0

  if [[ "$git_dir" != "$ROOT_DIR/.git" ]]; then
    mounts_ref+=(-v "$git_dir:$git_dir")
  fi
  if [[ -n "$git_common_dir" ]]; then
    git_common_dir="$(cd "$ROOT_DIR" && python3 - <<'PY' "$git_common_dir"
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"
    if [[ "$git_common_dir" != "$ROOT_DIR/.git" && "$git_common_dir" != "$git_dir" ]]; then
      mounts_ref+=(-v "$git_common_dir:$git_common_dir")
    fi
  fi
}

ensure_standard_env_registry_login() {
  local registry="ghcr.io"
  local username="${GHCR_WRITE_USERNAME:-${GHCR_USERNAME:-${GITHUB_ACTOR:-}}}"
  local token="${GHCR_WRITE_TOKEN:-${GHCR_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-}}}}"

  if [[ -z "$username" || -z "$token" ]]; then
    if command -v gh >/dev/null 2>&1 && gh auth status -t >/dev/null 2>&1; then
      username="${username:-$(gh api user -q .login 2>/dev/null || true)}"
      token="${token:-$(gh auth token 2>/dev/null || true)}"
    fi
  fi

  if [[ -z "$username" || -z "$token" ]]; then
    return 1
  fi

  printf '%s' "$token" | docker login "$registry" -u "$username" --password-stdin >/dev/null
}

ensure_standard_env_docker_daemon() {
  local stderr_file message
  stderr_file="$(mktemp)"
  if docker info >/dev/null 2>"$stderr_file"; then
    rm -f "$stderr_file"
    return 0
  fi

  message="$(
    tr '\n' ' ' <"$stderr_file" \
      | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//'
  )"
  rm -f "$stderr_file"
  echo "[strict-standard-env] docker daemon unavailable: ${message:-docker info failed}" >&2
  return 1
}

standard_env_needs_host_gateway() {
  case "$(uname -s)" in
    Darwin*|MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

resolve_standard_env_runtime_value() {
  local key="${1:-}"
  local value="${2:-}"

  if [[ -z "$value" ]] || ! standard_env_needs_host_gateway; then
    printf '%s\n' "$value"
    return 0
  fi

  python3 - "$key" "$value" "$STANDARD_ENV_HOST_GATEWAY" <<'PY'
from urllib.parse import urlsplit, urlunsplit
import sys

key, value, replacement_host = sys.argv[1:4]
loopback_hosts = {"127.0.0.1", "localhost"}

if key == "DATABASE_URL":
    parsed = urlsplit(value)
    if parsed.hostname not in loopback_hosts:
        print(value)
        raise SystemExit(0)
    if parsed.port is None:
        port_suffix = ""
    else:
        port_suffix = f":{parsed.port}"
    auth = ""
    if parsed.username is not None:
        auth = parsed.username
        if parsed.password is not None:
            auth += f":{parsed.password}"
        auth += "@"
    rebuilt = parsed._replace(netloc=f"{auth}{replacement_host}{port_suffix}")
    print(urlunsplit(rebuilt))
    raise SystemExit(0)

if key == "TEMPORAL_TARGET_HOST":
    host, separator, remainder = value.partition(":")
    if host in loopback_hosts and separator:
        print(f"{replacement_host}:{remainder}")
        raise SystemExit(0)

print(value)
PY
}

build_standard_env_image() {
  if [[ "${SOURCE_HARBOR_STANDARD_ENV_FORCE_REBUILD:-0}" != "1" ]] \
    && docker image inspect "${STRICT_CI_STANDARD_IMAGE_REPOSITORY}:local-debug" >/dev/null 2>&1; then
    STANDARD_ENV_IMAGE="${STRICT_CI_STANDARD_IMAGE_REPOSITORY}:local-debug"
    return 0
  fi

  "$ROOT_DIR/scripts/ci/build_standard_image.sh" --load --tag local-debug
  STANDARD_ENV_IMAGE="${STRICT_CI_STANDARD_IMAGE_REPOSITORY}:local-debug"
}

standard_env_can_use_local_fallback() {
  if is_truthy_env "${GITHUB_ACTIONS:-}"; then
    return 1
  fi
  is_truthy_env "$STANDARD_ENV_LOCAL_FALLBACK_ON_PULL_FAILURE"
}

use_local_standard_env_fallback() {
  local reason="${1:-unavailable}"
  echo "[strict-standard-env] local fallback: building repo-owned standard image because pinned image is ${reason}" >&2
  build_standard_env_image
  if ! docker image inspect "$STANDARD_ENV_IMAGE" >/dev/null 2>&1; then
    echo "[strict-standard-env] local fallback image is unavailable after build: $STANDARD_ENV_IMAGE" >&2
    return 1
  fi
}

run_in_standard_env() {
  local command=("$@")
  local runtime_database_url runtime_temporal_target_host
  local runtime_github_token
  local extra_mounts=()
  local pull_stderr_file pull_message

  runtime_database_url="$(resolve_standard_env_runtime_value DATABASE_URL "${DATABASE_URL:-}")"
  runtime_temporal_target_host="$(resolve_standard_env_runtime_value TEMPORAL_TARGET_HOST "${TEMPORAL_TARGET_HOST:-}")"
  runtime_github_token="${GITHUB_TOKEN:-}"
  if [[ -z "$runtime_github_token" ]] && command -v gh >/dev/null 2>&1 && gh auth status -t >/dev/null 2>&1; then
    runtime_github_token="$(gh auth token 2>/dev/null || true)"
  fi

  append_standard_env_git_mounts extra_mounts
  ensure_standard_env_docker_daemon
  if ! docker image inspect "$STANDARD_ENV_IMAGE" >/dev/null 2>&1; then
    if ! ensure_standard_env_registry_login; then
      if standard_env_can_use_local_fallback; then
        use_local_standard_env_fallback "unavailable locally because no GHCR pull credentials are configured"
      else
        echo "[strict-standard-env] missing GHCR credentials; set GHCR_WRITE_USERNAME/GHCR_WRITE_TOKEN or GHCR_USERNAME/GHCR_TOKEN, or authenticate gh CLI before pulling $STANDARD_ENV_IMAGE" >&2
        return 1
      fi
    fi
    if ! docker image inspect "$STANDARD_ENV_IMAGE" >/dev/null 2>&1; then
      pull_stderr_file="$(mktemp)"
      if ! docker pull "$STANDARD_ENV_IMAGE" >/dev/null 2>"$pull_stderr_file"; then
        pull_message="$(
          tr '\n' ' ' <"$pull_stderr_file" \
            | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//'
        )"
        rm -f "$pull_stderr_file"
        echo "[strict-standard-env] failed to pull required image: $STANDARD_ENV_IMAGE" >&2
        if [[ -n "$pull_message" ]]; then
          echo "[strict-standard-env] docker pull detail: $pull_message" >&2
        fi
        if standard_env_can_use_local_fallback; then
          use_local_standard_env_fallback "unavailable from GHCR"
        else
          return 1
        fi
      else
        rm -f "$pull_stderr_file"
      fi
      if ! docker image inspect "$STANDARD_ENV_IMAGE" >/dev/null 2>&1; then
        echo "[strict-standard-env] required image is unavailable after pull: $STANDARD_ENV_IMAGE" >&2
        return 1
      fi
    fi
  fi

  docker run --rm --init \
    --network host \
    -v "$ROOT_DIR:$STANDARD_ENV_WORKDIR" \
    "${extra_mounts[@]}" \
    -w "$STANDARD_ENV_WORKDIR" \
    -e SOURCE_HARBOR_IN_STANDARD_ENV=1 \
    -e CI="${CI:-}" \
    -e GITHUB_ACTIONS="${GITHUB_ACTIONS:-}" \
    -e PYTHONPATH="${PYTHONPATH:-}" \
    -e DATABASE_URL="$runtime_database_url" \
    -e TEMPORAL_TARGET_HOST="$runtime_temporal_target_host" \
    -e TEMPORAL_NAMESPACE="${TEMPORAL_NAMESPACE:-}" \
    -e TEMPORAL_TASK_QUEUE="${TEMPORAL_TASK_QUEUE:-}" \
    -e PYTHON_TESTS_XDIST_WORKERS="${PYTHON_TESTS_XDIST_WORKERS:-}" \
    -e PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$STRICT_CI_PLAYWRIGHT_BROWSERS_PATH}" \
    -e UV_CACHE_DIR="${UV_CACHE_DIR:-$STRICT_CI_UV_CACHE_DIR}" \
    -e GITHUB_TOKEN="$runtime_github_token" \
    "$STANDARD_ENV_IMAGE" \
    "${command[@]}"
}

ensure_external_uv_project_environment() {
  local root_dir="${1:-}"
  local current_value="${UV_PROJECT_ENVIRONMENT:-}"
  local cache_root="${SOURCE_HARBOR_CACHE_ROOT:-${HOME}/.cache/sourceharbor}"
  local fallback="${cache_root}/project-venv"
  local legacy_fallback="${HOME}/.sourceharbor/project-venv"

  if [[ -z "$root_dir" ]]; then
    if [[ "$current_value" == "$legacy_fallback" ]]; then
      export UV_PROJECT_ENVIRONMENT="$fallback"
    else
      export UV_PROJECT_ENVIRONMENT="${current_value:-$fallback}"
    fi
    return 0
  fi

  if [[ -z "$current_value" ]]; then
    export UV_PROJECT_ENVIRONMENT="$fallback"
    return 0
  fi

  case "$current_value" in
    "$legacy_fallback"|"$HOME/.sourceharbor"/project-venv)
      export UV_PROJECT_ENVIRONMENT="$fallback"
      ;;
    "$root_dir"/*|.venv|./.venv|.runtime-cache/*)
      export UV_PROJECT_ENVIRONMENT="$fallback"
      ;;
  esac
}
