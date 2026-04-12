ARG STRICT_CI_BASE_IMAGE=mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39
FROM ${STRICT_CI_BASE_IMAGE}

ARG STRICT_CI_NODE_MAJOR=22
ARG STRICT_CI_UV_VERSION=0.10.7
ARG STRICT_CI_TEMPORAL_CLI_VERSION=1.5.1
ARG STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_AMD64=ddc95e08b0b076efd4ea9733a3f488eb7d2be875f8834e616cd2a37358b4852d
ARG STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_ARM64=bd1b0db9f18b051026de8bf6cc1505f2510f14bbb7a8b9a4a91fff46c77454f5

LABEL org.opencontainers.image.source="https://github.com/xiaojiou176-open/sourceharbor"

ENV PLAYWRIGHT_BROWSERS_PATH=/tmp/ci-cache/ms-playwright

RUN rm -f /etc/apt/sources.list.d/yarn.list \
  && find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) -print0 \
    | xargs -0 sed -i 's|http://deb.debian.org|https://deb.debian.org|g; s|http://security.debian.org|https://security.debian.org|g' \
  && apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates git gh gnupg jq ripgrep tar \
  && install -d -m 0755 /etc/apt/keyrings \
  && key_tmp="$(mktemp)" \
  && curl --http1.1 --retry 5 --retry-all-errors --retry-delay 2 -fL \
    "https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key" \
    -o "${key_tmp}" \
  && test -s "${key_tmp}" \
  && gpg --dearmor --batch --yes -o /etc/apt/keyrings/nodesource.gpg "${key_tmp}" \
  && rm -f "${key_tmp}" \
  && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${STRICT_CI_NODE_MAJOR}.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    nodejs \
    postgresql-client \
    sqlite3 \
    unzip \
  && rm -rf /var/lib/apt/lists/* \
  && python3 -m pip install --no-cache-dir "uv==${STRICT_CI_UV_VERSION}" \
  && arch="$(uname -m)" \
  && case "$arch" in \
      x86_64|amd64) temporal_arch="amd64"; expected_sha="${STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_AMD64}" ;; \
      aarch64|arm64) temporal_arch="arm64"; expected_sha="${STRICT_CI_TEMPORAL_CLI_SHA256_LINUX_ARM64}" ;; \
      *) echo "Unsupported architecture: ${arch}" >&2; exit 1 ;; \
    esac \
  && tmpdir="$(mktemp -d)" \
  && archive="temporal_cli_${STRICT_CI_TEMPORAL_CLI_VERSION}_linux_${temporal_arch}.tar.gz" \
  && curl --retry 5 --retry-all-errors --retry-delay 2 -fL "https://github.com/temporalio/cli/releases/download/v${STRICT_CI_TEMPORAL_CLI_VERSION}/${archive}" -o "${tmpdir}/${archive}" \
  && echo "${expected_sha}  ${tmpdir}/${archive}" | sha256sum -c - \
  && tar -xzf "${tmpdir}/${archive}" -C "${tmpdir}" temporal \
  && install -m 0755 "${tmpdir}/temporal" /usr/local/bin/temporal \
  && uv --version \
  && uv run --with playwright python -m playwright install --with-deps chromium firefox webkit \
  && uv --version \
  && node --version \
  && npm --version \
  && temporal --version

ENV PATH="${PATH}"
