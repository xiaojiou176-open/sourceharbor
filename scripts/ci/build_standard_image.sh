#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PUSH_IMAGE="0"
LOAD_IMAGE="0"
TAG_OVERRIDE=""
METADATA_FILE=""
PLATFORMS="${SOURCE_HARBOR_STANDARD_ENV_BUILD_PLATFORMS:-linux/amd64,linux/arm64}"

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
  local arch="${SOURCE_HARBOR_STANDARD_ENV_LOAD_PLATFORM_ARCH:-$(uname -m)}"
  case "$arch" in
    x86_64|amd64)
      printf 'linux/amd64\n'
      ;;
    arm64|aarch64)
      printf 'linux/arm64\n'
      ;;
    *)
      echo "[build-ci-standard-image] unsupported local load architecture: $arch" >&2
      exit 2
      ;;
  esac
}

usage() {
  cat <<'EOF'
Usage: ./scripts/ci/build_standard_image.sh [--push] [--load] [--tag <tag>] [--metadata-file <path>]

Build the SourceHarbor strict CI/devcontainer standard image.
Primary role: repo CI, devcontainer parity, and the GHCR infrastructure image
publish path described by the strict CI contract.
This is not a newcomer-facing product container installer or public runtime
distribution promise.
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
      echo "[build-ci-standard-image] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

eval "$(python3 "$ROOT_DIR/scripts/ci/contract.py" shell-exports)"

image_repository="$STRICT_CI_STANDARD_IMAGE_REPOSITORY"
image_tag="$STRICT_CI_STANDARD_IMAGE_TAG"
if [[ -n "$TAG_OVERRIDE" ]]; then
  image_tag="$TAG_OVERRIDE"
fi

build_args=(
  --build-arg "STRICT_CI_BASE_IMAGE=$(python3 "$ROOT_DIR/scripts/ci/contract.py" get toolchain.base_image)"
  --build-arg "STRICT_CI_NODE_MAJOR=$STRICT_CI_NODE_MAJOR"
  --build-arg "STRICT_CI_UV_VERSION=$STRICT_CI_UV_VERSION"
  --build-arg "STRICT_CI_TEMPORAL_CLI_VERSION=$STRICT_CI_TEMPORAL_CLI_VERSION"
  --build-arg "STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_AMD64=$STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_AMD64"
  --build-arg "STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_ARM64=$STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_ARM64"
)

common_args=(
  --file "$STRICT_CI_STANDARD_IMAGE_DOCKERFILE"
  --tag "${image_repository}:${image_tag}"
)

source_repository_url="$(resolve_source_repository_url)"
if [[ -n "$source_repository_url" ]]; then
  common_args+=(
    --label "org.opencontainers.image.source=${source_repository_url}"
  )
fi

if [[ "$LOAD_IMAGE" == "1" ]]; then
  PLATFORMS="$(resolve_local_load_platform)"
fi

if [[ -n "$METADATA_FILE" ]]; then
  mkdir -p "$(dirname "$METADATA_FILE")"
fi

metadata_args=()
if [[ -n "$METADATA_FILE" ]]; then
  metadata_args=(--metadata-file "$METADATA_FILE")
fi

if [[ "$PUSH_IMAGE" == "1" ]]; then
  docker buildx build \
    "${common_args[@]}" \
    --platform "$PLATFORMS" \
    --push \
    "${metadata_args[@]}" \
    "${build_args[@]}" \
    "$ROOT_DIR"
elif [[ "$LOAD_IMAGE" == "1" ]]; then
  docker build \
    "${common_args[@]}" \
    --platform "$PLATFORMS" \
    "${build_args[@]}" \
    "$ROOT_DIR"
else
  docker buildx build \
    "${common_args[@]}" \
    --platform "$PLATFORMS" \
    "${metadata_args[@]}" \
    "${build_args[@]}" \
    "$ROOT_DIR"
fi
