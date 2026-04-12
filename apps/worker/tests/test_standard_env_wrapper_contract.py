from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_standard_env_probe(
    *,
    database_url: str,
    temporal_target_host: str,
    simulated_uname: str | None = None,
) -> subprocess.CompletedProcess[str]:
    root = _repo_root()
    script = """source scripts/lib/standard_env.sh
if [[ -n \"${SIMULATED_UNAME:-}\" ]]; then
  uname() {
    printf '%s\\n' \"$SIMULATED_UNAME\"
  }
fi
route_database_url=\"$(resolve_standard_env_runtime_value DATABASE_URL \"$DATABASE_URL\")\"
route_temporal_target_host=\"$(resolve_standard_env_runtime_value TEMPORAL_TARGET_HOST \"$TEMPORAL_TARGET_HOST\")\"
printf 'DATABASE_URL=%s\\n' \"$route_database_url\"
printf 'TEMPORAL_TARGET_HOST=%s\\n' \"$route_temporal_target_host\"
"""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "DATABASE_URL": database_url,
        "TEMPORAL_TARGET_HOST": temporal_target_host,
        "SIMULATED_UNAME": simulated_uname or "",
    }
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_standard_env_local_fallback_probe(
    *, simulated_pull_error: str
) -> subprocess.CompletedProcess[str]:
    root = _repo_root()
    script = f"""source scripts/lib/standard_env.sh
STANDARD_ENV_IMAGE="ghcr.io/example/standard-env@sha256:deadbeef"
STRICT_CI_STANDARD_IMAGE_REPOSITORY="ghcr.io/example/standard-env"
STANDARD_ENV_WORKDIR="/workspace"
fallback_invoked=0
docker() {{
  if [[ "${{1:-}}" == "info" ]]; then
    return 0
  fi
  if [[ "${{1:-}}" == "image" && "${{2:-}}" == "inspect" ]]; then
    if [[ "${{3:-}}" == "ghcr.io/example/standard-env:local-debug" ]]; then
      return 0
    fi
    return 1
  fi
  if [[ "${{1:-}}" == "pull" ]]; then
    printf '%s\\n' "{simulated_pull_error}" >&2
    return 1
  fi
  if [[ "${{1:-}}" == "run" ]]; then
    printf 'RUN_IMAGE=%s\\n' "${{22:-}}"
    return 0
  fi
  if [[ "${{1:-}}" == "login" ]]; then
    return 0
  fi
  printf 'unexpected docker invocation: %s\\n' "$*" >&2
  return 1
}}
build_standard_env_image() {{
  fallback_invoked=1
  STANDARD_ENV_IMAGE="ghcr.io/example/standard-env:local-debug"
}}
ensure_standard_env_registry_login() {{
  return 0
}}
run_in_standard_env bash -lc true
rc=$?
printf 'FALLBACK=%s\\n' "$fallback_invoked"
exit "$rc"
"""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SOURCE_HARBOR_STANDARD_ENV_LOCAL_FALLBACK_ON_PULL_FAILURE": "1",
        "GITHUB_ACTIONS": "",
    }
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_build_ci_standard_image(
    *,
    args: list[str],
    simulated_arch: str,
) -> subprocess.CompletedProcess[str]:
    root = _repo_root()
    with tempfile.TemporaryDirectory() as tmp_dir:
        bin_dir = Path(tmp_dir)
        docker_log = bin_dir / "docker-args.txt"

        (bin_dir / "python3").write_text(
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-" ]]; then
  printf 'https://github.com/xiaojiou176-open/sourceharbor\\n'
  exit 0
fi
if [[ "${2:-}" == "shell-exports" ]]; then
  cat <<'EOF'
export STRICT_CI_STANDARD_IMAGE_REPOSITORY=ghcr.io/example/standard-env
export STRICT_CI_STANDARD_IMAGE_TAG=ci
export STRICT_CI_STANDARD_IMAGE_DOCKERFILE=.devcontainer/Dockerfile
export STRICT_CI_NODE_MAJOR=22
export STRICT_CI_UV_VERSION=0.7.0
export STRICT_CI_TEMPORAL_CLI_VERSION=1.0.0
export STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_AMD64=amd64-sha
export STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_ARM64=arm64-sha
EOF
  exit 0
fi
if [[ "${2:-}" == "get" && "${3:-}" == "toolchain.base_image" ]]; then
  printf 'ubuntu:24.04\\n'
  exit 0
fi
echo "unexpected python3 invocation: $*" >&2
exit 1
""",
            encoding="utf-8",
        )
        (bin_dir / "docker").write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$@" > "{docker_log}"
""",
            encoding="utf-8",
        )
        (bin_dir / "uname").write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "{simulated_arch}"
""",
            encoding="utf-8",
        )
        for stub in ("python3", "docker", "uname"):
            (bin_dir / stub).chmod(0o755)

        env = {
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        }
        result = subprocess.run(
            ["bash", "scripts/ci/build_standard_image.sh", *args],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if docker_log.exists():
            result.docker_args = docker_log.read_text(encoding="utf-8").splitlines()
        else:
            result.docker_args = []
        return result


def test_standard_env_wrapper_and_helper_contract_exist() -> None:
    root = _repo_root()
    runner = (root / "scripts" / "ci" / "run_in_standard_env.sh").read_text(encoding="utf-8")
    helper = (root / "scripts" / "lib" / "standard_env.sh").read_text(encoding="utf-8")

    assert 'source "$ROOT_DIR/scripts/lib/standard_env.sh"' in runner
    assert 'ALLOW_LOCAL_BUILD="${SOURCE_HARBOR_STANDARD_ENV_ALLOW_LOCAL_BUILD:-0}"' in runner
    assert "if is_running_inside_standard_env; then" in runner
    assert 'if [[ "$ALLOW_LOCAL_BUILD" == "1" ]]; then' in runner
    assert 'run_in_standard_env "$@"' in runner

    assert 'eval "$(python3 "$ROOT_DIR/scripts/ci/contract.py" shell-exports)"' in helper
    assert (
        'STANDARD_ENV_IMAGE="${SOURCE_HARBOR_STANDARD_ENV_IMAGE:-$STRICT_CI_STANDARD_IMAGE_REF}"'
        in helper
    )
    assert (
        'STANDARD_ENV_DOCKERFILE="${SOURCE_HARBOR_STANDARD_ENV_DOCKERFILE:-$ROOT_DIR/$STRICT_CI_STANDARD_IMAGE_DOCKERFILE}"'
        in helper
    )
    assert (
        'STANDARD_ENV_WORKDIR="${SOURCE_HARBOR_STANDARD_ENV_WORKDIR:-$STRICT_CI_STANDARD_IMAGE_WORKDIR}"'
        in helper
    )
    assert 'docker pull "$STANDARD_ENV_IMAGE"' in helper
    assert "GHCR_WRITE_USERNAME:-${GHCR_USERNAME:-${GITHUB_ACTOR:-}}" in helper
    assert "GHCR_WRITE_TOKEN:-${GHCR_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-}}}" in helper
    assert "gh auth status -t" in helper
    assert "gh auth token" in helper
    assert (
        'STANDARD_ENV_LOCAL_FALLBACK_ON_PULL_FAILURE="${SOURCE_HARBOR_STANDARD_ENV_LOCAL_FALLBACK_ON_PULL_FAILURE:-1}"'
        in helper
    )
    assert "standard_env_can_use_local_fallback() {" in helper
    assert "use_local_standard_env_fallback() {" in helper
    assert "local fallback: building repo-owned standard image because pinned image is" in helper
    assert "-e SOURCE_HARBOR_IN_STANDARD_ENV=1" in helper
    assert (
        'STANDARD_ENV_HOST_GATEWAY="${SOURCE_HARBOR_STANDARD_ENV_HOST_GATEWAY:-host.docker.internal}"'
        in helper
    )
    assert "resolve_standard_env_runtime_value() {" in helper
    assert (
        'runtime_database_url="$(resolve_standard_env_runtime_value DATABASE_URL "${DATABASE_URL:-}")"'
        in helper
    )
    assert (
        'runtime_temporal_target_host="$(resolve_standard_env_runtime_value TEMPORAL_TARGET_HOST "${TEMPORAL_TARGET_HOST:-}")"'
        in helper
    )
    assert '-e DATABASE_URL="$runtime_database_url"' in helper
    assert '-e TEMPORAL_TARGET_HOST="$runtime_temporal_target_host"' in helper
    assert '-e PYTHONPATH="${PYTHONPATH:-}"' in helper
    assert '-e TEMPORAL_NAMESPACE="${TEMPORAL_NAMESPACE:-}"' in helper
    assert '-e TEMPORAL_TASK_QUEUE="${TEMPORAL_TASK_QUEUE:-}"' in helper
    assert '-e PYTHON_TESTS_XDIST_WORKERS="${PYTHON_TESTS_XDIST_WORKERS:-}"' in helper


def test_standard_env_wrapper_falls_back_to_local_debug_image_when_local_pull_is_forbidden() -> (
    None
):
    result = _run_standard_env_local_fallback_probe(
        simulated_pull_error="Error response from daemon: unexpected status from HEAD request: 403 Forbidden",
    )

    assert (
        "failed to pull required image: ghcr.io/example/standard-env@sha256:deadbeef"
        in result.stderr
    )
    assert (
        "docker pull detail: Error response from daemon: unexpected status from HEAD request: 403 Forbidden"
        in result.stderr
    )
    assert (
        "local fallback: building repo-owned standard image because pinned image is unavailable from GHCR"
        in result.stderr
    )
    assert "FALLBACK=1" in result.stdout


def test_build_ci_standard_image_uses_single_platform_for_local_load() -> None:
    result = _run_build_ci_standard_image(
        args=["--load", "--tag", "local-debug"], simulated_arch="arm64"
    )

    assert result.returncode == 0, result.stderr
    assert result.docker_args[:2] == ["build", "--file"]
    assert "buildx" not in result.docker_args
    assert "--load" not in result.docker_args
    assert "--push" not in result.docker_args
    assert "--tag" in result.docker_args
    assert (
        result.docker_args[result.docker_args.index("--tag") + 1]
        == "ghcr.io/example/standard-env:local-debug"
    )
    assert "--platform" in result.docker_args
    assert result.docker_args[result.docker_args.index("--platform") + 1] == "linux/arm64"
    labels = [
        result.docker_args[index + 1]
        for index, value in enumerate(result.docker_args[:-1])
        if value == "--label"
    ]
    assert (
        "org.opencontainers.image.source=https://github.com/xiaojiou176-open/sourceharbor" in labels
    )


def test_build_ci_standard_image_default_path_preserves_buildx_multi_platform_semantics() -> None:
    result = _run_build_ci_standard_image(args=[], simulated_arch="arm64")

    assert result.returncode == 0, result.stderr
    assert result.docker_args[:3] == ["buildx", "build", "--file"]
    assert "--push" not in result.docker_args
    assert "--platform" in result.docker_args
    assert (
        result.docker_args[result.docker_args.index("--platform") + 1] == "linux/amd64,linux/arm64"
    )
    labels = [
        result.docker_args[index + 1]
        for index, value in enumerate(result.docker_args[:-1])
        if value == "--label"
    ]
    assert (
        "org.opencontainers.image.source=https://github.com/xiaojiou176-open/sourceharbor" in labels
    )


def test_build_ci_standard_image_preserves_multi_platform_push() -> None:
    result = _run_build_ci_standard_image(args=["--push"], simulated_arch="arm64")

    assert result.returncode == 0, result.stderr
    assert result.docker_args[:3] == ["buildx", "build", "--file"]
    assert "--push" in result.docker_args
    assert "--load" not in result.docker_args
    assert "--platform" in result.docker_args
    assert (
        result.docker_args[result.docker_args.index("--platform") + 1] == "linux/amd64,linux/arm64"
    )


def test_standard_env_wrapper_rewrites_loopback_backend_targets_for_container_runtime() -> None:
    result = _run_standard_env_probe(
        database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sourceharbor_pytests",
        temporal_target_host="localhost:7233",
        simulated_uname="Darwin",
    )

    assert result.returncode == 0, result.stderr
    assert (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@host.docker.internal:5432/sourceharbor_pytests"
        in result.stdout
    )
    assert "TEMPORAL_TARGET_HOST=host.docker.internal:7233" in result.stdout


def test_standard_env_wrapper_preserves_non_loopback_backend_targets() -> None:
    result = _run_standard_env_probe(
        database_url="postgresql+psycopg://postgres:postgres@postgres.internal:5432/sourceharbor_pytests",
        temporal_target_host="temporal.internal:7233",
        simulated_uname="Darwin",
    )

    assert result.returncode == 0, result.stderr
    assert (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres.internal:5432/sourceharbor_pytests"
        in result.stdout
    )
    assert "TEMPORAL_TARGET_HOST=temporal.internal:7233" in result.stdout


def test_standard_env_wrapper_preserves_loopback_targets_on_linux() -> None:
    result = _run_standard_env_probe(
        database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sourceharbor_pytests",
        temporal_target_host="127.0.0.1:7233",
        simulated_uname="Linux",
    )

    assert result.returncode == 0, result.stderr
    assert (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sourceharbor_pytests"
        in result.stdout
    )
    assert "TEMPORAL_TARGET_HOST=127.0.0.1:7233" in result.stdout


def test_devcontainer_dockerfile_mitigates_broken_yarn_apt_source_before_update() -> None:
    dockerfile = (_repo_root() / ".devcontainer" / "Dockerfile").read_text(encoding="utf-8")

    assert "rm -f /etc/apt/sources.list.d/yarn.list" in dockerfile
    assert dockerfile.index("rm -f /etc/apt/sources.list.d/yarn.list") < dockerfile.index(
        "apt-get update"
    )


def test_devcontainer_dockerfile_installs_uv_for_repo_owned_wrapper_scripts() -> None:
    dockerfile = (_repo_root() / ".devcontainer" / "Dockerfile").read_text(encoding="utf-8")

    assert 'python3 -m pip install --no-cache-dir "uv==${STRICT_CI_UV_VERSION}"' in dockerfile
    assert "uv --version" in dockerfile


def test_devcontainer_dockerfile_pins_nodesource_node_22_for_standard_env() -> None:
    dockerfile = (_repo_root() / ".devcontainer" / "Dockerfile").read_text(encoding="utf-8")

    assert "STRICT_CI_NODE_MAJOR=22" in dockerfile
    assert "https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key" in dockerfile
    assert "--http1.1 --retry 5 --retry-all-errors --retry-delay 2 -fL" in dockerfile
    assert 'key_tmp="$(mktemp)"' in dockerfile
    assert (
        'gpg --dearmor --batch --yes -o /etc/apt/keyrings/nodesource.gpg "${key_tmp}"' in dockerfile
    )
    assert "https://deb.nodesource.com/node_${STRICT_CI_NODE_MAJOR}.x nodistro main" in dockerfile
    assert dockerfile.index(
        "https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key"
    ) < dockerfile.index("apt-get install -y --no-install-recommends \\\n    nodejs")
    assert "nodejs" in dockerfile
