FROM python:3.12-slim-bookworm

ARG SOURCEHARBOR_WHEEL
ARG SOURCEHARBOR_VERSION=0.1.19
ARG SOURCEHARBOR_VCS_REF=unknown
ARG SOURCEHARBOR_BUILD_DATE=unknown

LABEL org.opencontainers.image.title="SourceHarbor API"
LABEL org.opencontainers.image.description="Public API image for SourceHarbor's FastAPI surface."
LABEL org.opencontainers.image.url="https://github.com/xiaojiou176-open/sourceharbor"
LABEL org.opencontainers.image.documentation="https://github.com/xiaojiou176-open/sourceharbor/tree/main/docs"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/xiaojiou176-open/sourceharbor"
LABEL org.opencontainers.image.vendor="SourceHarbor Maintainers"
LABEL org.opencontainers.image.version="${SOURCEHARBOR_VERSION}"
LABEL org.opencontainers.image.revision="${SOURCEHARBOR_VCS_REF}"
LABEL org.opencontainers.image.created="${SOURCEHARBOR_BUILD_DATE}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOURCE_HARBOR_RUNTIME_ROOT=/opt/sourceharbor-runtime \
    SOURCE_HARBOR_CACHE_ROOT=/var/lib/sourceharbor \
    PIPELINE_ARTIFACT_ROOT=/var/lib/sourceharbor/artifacts \
    SQLITE_STATE_PATH=/var/lib/sourceharbor/state/api_state.db \
    DATABASE_URL=postgresql+psycopg://sourceharbor:sourceharbor@postgres:5432/sourceharbor \
    TEMPORAL_TARGET_HOST=temporal:7233 \
    TEMPORAL_NAMESPACE=default \
    TEMPORAL_TASK_QUEUE=sourceharbor-worker \
    APP_VERSION=${SOURCEHARBOR_VERSION}

WORKDIR /opt/sourceharbor-runtime

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /var/lib/sourceharbor/state /var/lib/sourceharbor/artifacts /opt/sourceharbor-runtime/scripts

COPY ${SOURCEHARBOR_WHEEL} /tmp/
COPY config /opt/sourceharbor-runtime/config
COPY scripts/runtime /opt/sourceharbor-runtime/scripts/runtime

RUN python -m pip install --no-cache-dir "/tmp/${SOURCEHARBOR_WHEEL}" \
  && rm -f "/tmp/${SOURCEHARBOR_WHEEL}" \
  && python - <<'PY'
from __future__ import annotations

import shutil
import site
from pathlib import Path

for root in [Path(path) for path in site.getsitepackages()]:
    for relative in (
        "apps/web",
        "apps/worker",
        "apps/api/tests",
        "apps/mcp/tests",
    ):
        target = root / relative
        if target.exists():
            shutil.rmtree(target)
    for cache_dir in root.rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir)
PY

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["python", "-m", "uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
