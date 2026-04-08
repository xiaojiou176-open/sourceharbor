#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PUSH_IMAGE="0"
LOAD_IMAGE="0"
TAG_OVERRIDE=""
METADATA_FILE=""
PLATFORMS="${SOURCE_HARBOR_PUBLIC_IMAGE_BUILD_PLATFORMS:-linux/amd64,linux/arm64}"
IMAGE_REPOSITORY="${SOURCE_HARBOR_PUBLIC_API_IMAGE_REPOSITORY:-ghcr.io/xiaojiou176-open/sourceharbor-api}"
STAGING_ROOT="$ROOT_DIR/.runtime-cache/tmp/public-image-audit"
CONTEXT_DIR="$STAGING_ROOT/build-context"
DIST_DIR="$STAGING_ROOT/dist"

resolve_version() {
  python3 - <<'PY'
from pathlib import Path
import tomllib

payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(payload["project"]["version"])
PY
}

resolve_source_repository_url() {
  if [[ -n "${GITHUB_SERVER_URL:-}" && -n "${GITHUB_REPOSITORY:-}" ]]; then
    printf '%s/%s\n' "${GITHUB_SERVER_URL%/}" "${GITHUB_REPOSITORY}"
    return 0
  fi

  local remote_url
  remote_url="$(git config --get remote.origin.url 2>/dev/null || true)"
  if [[ -z "$remote_url" ]]; then
    return 0
  fi

  python3 - <<'PY' "$remote_url"
import re
import sys

remote = sys.argv[1]
match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote)
if not match:
    print("", end="")
    raise SystemExit(0)
print(f"https://github.com/{match.group('owner')}/{match.group('repo')}")
PY
}

resolve_local_load_platform() {
  local arch="${SOURCE_HARBOR_PUBLIC_IMAGE_LOAD_PLATFORM_ARCH:-$(uname -m)}"
  case "$arch" in
    x86_64|amd64)
      printf 'linux/amd64\n'
      ;;
    arm64|aarch64)
      printf 'linux/arm64\n'
      ;;
    *)
      echo "[build-public-api-image] unsupported local load architecture: $arch" >&2
      exit 2
      ;;
  esac
}

usage() {
  cat <<'EOF'
Usage: ./scripts/ci/build_public_api_image.sh [--push] [--load] [--tag <tag>] [--metadata-file <path>]

Build the SourceHarbor public API image.
This is the newcomer-facing API container lane, separate from the strict CI
standard image used for CI/devcontainer parity.
EOF
}

while (($# > 0)); do
  case "$1" in
    --push)
      PUSH_IMAGE="1"
      shift
      ;;
    --load)
      LOAD_IMAGE="1"
      shift
      ;;
    --tag)
      TAG_OVERRIDE="${2:-}"
      shift 2
      ;;
    --metadata-file)
      METADATA_FILE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[build-public-api-image] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$PUSH_IMAGE" == "1" && "$LOAD_IMAGE" == "1" ]]; then
  echo "[build-public-api-image] --push and --load are mutually exclusive" >&2
  exit 2
fi

SOURCEHARBOR_VERSION="$(resolve_version)"
SOURCEHARBOR_VCS_REF="$(git rev-parse HEAD 2>/dev/null || printf 'unknown\n')"
SOURCEHARBOR_BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
SOURCE_REPOSITORY_URL="$(resolve_source_repository_url)"
if [[ -n "$TAG_OVERRIDE" ]]; then
  DEFAULT_TAG="$TAG_OVERRIDE"
else
  DEFAULT_TAG="$SOURCEHARBOR_VERSION"
fi

rm -rf "$CONTEXT_DIR" "$DIST_DIR"
mkdir -p "$CONTEXT_DIR" "$DIST_DIR"

uv build --wheel --out-dir "$DIST_DIR"

wheel_path="$(find "$DIST_DIR" -maxdepth 1 -type f -name "sourceharbor-${SOURCEHARBOR_VERSION}-*.whl" | head -n 1)"
if [[ -z "$wheel_path" || ! -f "$wheel_path" ]]; then
  echo "[build-public-api-image] failed to locate built wheel for version ${SOURCEHARBOR_VERSION}" >&2
  exit 1
fi

wheel_name="$(basename "$wheel_path")"
cp "$ROOT_DIR/infra/docker/sourceharbor-api.Dockerfile" "$CONTEXT_DIR/Dockerfile"
cp "$wheel_path" "$CONTEXT_DIR/$wheel_name"
cp -R "$ROOT_DIR/config" "$CONTEXT_DIR/config"
mkdir -p "$CONTEXT_DIR/scripts"
cp -R "$ROOT_DIR/scripts/runtime" "$CONTEXT_DIR/scripts/runtime"

build_args=(
  --build-arg "SOURCEHARBOR_WHEEL=${wheel_name}"
  --build-arg "SOURCEHARBOR_VERSION=${SOURCEHARBOR_VERSION}"
  --build-arg "SOURCEHARBOR_VCS_REF=${SOURCEHARBOR_VCS_REF}"
  --build-arg "SOURCEHARBOR_BUILD_DATE=${SOURCEHARBOR_BUILD_DATE}"
)

common_args=(
  --file "$CONTEXT_DIR/Dockerfile"
)

if [[ -n "$SOURCE_REPOSITORY_URL" ]]; then
  common_args+=(
    --label "org.opencontainers.image.source=${SOURCE_REPOSITORY_URL}"
  )
fi

if [[ -n "$METADATA_FILE" ]]; then
  mkdir -p "$(dirname "$METADATA_FILE")"
fi

metadata_args=()
if [[ -n "$METADATA_FILE" ]]; then
  metadata_args=(--metadata-file "$METADATA_FILE")
fi

if [[ "$LOAD_IMAGE" == "1" ]]; then
  PLATFORMS="$(resolve_local_load_platform)"
  docker build \
    "${common_args[@]}" \
    --platform "$PLATFORMS" \
    --tag "${IMAGE_REPOSITORY}:${DEFAULT_TAG}" \
    "${build_args[@]}" \
    "$CONTEXT_DIR"
elif [[ "$PUSH_IMAGE" == "1" ]]; then
  docker buildx build \
    "${common_args[@]}" \
    --platform "$PLATFORMS" \
    --push \
    "${metadata_args[@]}" \
    --tag "${IMAGE_REPOSITORY}:${SOURCEHARBOR_VCS_REF}" \
    --tag "${IMAGE_REPOSITORY}:${SOURCEHARBOR_VERSION}" \
    --tag "${IMAGE_REPOSITORY}:latest" \
    "${build_args[@]}" \
    "$CONTEXT_DIR"
else
  docker buildx build \
    "${common_args[@]}" \
    --platform "$PLATFORMS" \
    "${metadata_args[@]}" \
    --tag "${IMAGE_REPOSITORY}:${DEFAULT_TAG}" \
    "${build_args[@]}" \
    "$CONTEXT_DIR"
fi
