#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

IMAGE_REPOSITORY="${SOURCE_HARBOR_PUBLIC_API_IMAGE_REPOSITORY:-ghcr.io/xiaojiou176-open/sourceharbor-api}"
IMAGE_TAG="${SOURCE_HARBOR_PUBLIC_API_IMAGE_SMOKE_TAG:-local-smoke}"
HOST_PORT="${SOURCE_HARBOR_PUBLIC_API_IMAGE_SMOKE_PORT:-18082}"
CONTAINER_NAME="sourceharbor-api-smoke-${$}"
API_URL="http://127.0.0.1:${HOST_PORT}/healthz"

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}

trap cleanup EXIT

"$ROOT_DIR/scripts/ci/build_public_api_image.sh" --load --tag "$IMAGE_TAG"

docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${HOST_PORT}:8000" \
  "${IMAGE_REPOSITORY}:${IMAGE_TAG}" >/dev/null

python3 - <<'PY' "$API_URL"
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

url = sys.argv[1]
deadline = time.time() + 60
last_error = "no response"

while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = response.read().decode("utf-8", "replace")
            if response.status == 200 and '"status":"ok"' in payload.replace(" ", ""):
                print(payload)
                raise SystemExit(0)
            last_error = f"unexpected response: status={response.status} body={payload[:200]}"
    except (urllib.error.URLError, ConnectionResetError, OSError) as exc:
        last_error = str(exc)
    time.sleep(1)

print(last_error, file=sys.stderr)
raise SystemExit(1)
PY
