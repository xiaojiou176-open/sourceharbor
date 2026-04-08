FROM python:3.12-slim-bookworm

ARG SOURCEHARBOR_WHEEL
ARG SOURCEHARBOR_VERSION=0.1.14
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
    PYTHONPATH=/app \
    SOURCE_HARBOR_CACHE_ROOT=/var/lib/sourceharbor \
    PIPELINE_ARTIFACT_ROOT=/var/lib/sourceharbor/artifacts \
    SQLITE_STATE_PATH=/var/lib/sourceharbor/state/api_state.db \
    DATABASE_URL=postgresql+psycopg://sourceharbor:sourceharbor@postgres:5432/sourceharbor \
    TEMPORAL_TARGET_HOST=temporal:7233 \
    TEMPORAL_NAMESPACE=default \
    TEMPORAL_TASK_QUEUE=sourceharbor-worker \
    APP_VERSION=${SOURCEHARBOR_VERSION}

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /var/lib/sourceharbor/state /var/lib/sourceharbor/artifacts

COPY ${SOURCEHARBOR_WHEEL} /tmp/
COPY apps /app/apps
COPY integrations /app/integrations
COPY config /app/config

RUN python -m pip install --no-cache-dir "/tmp/${SOURCEHARBOR_WHEEL}" \
  && rm -f "/tmp/${SOURCEHARBOR_WHEEL}"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["python", "-m", "uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
