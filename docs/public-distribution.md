# Public Distribution Status

Use it like a shipping ledger, not like a launch post.

## Current Public Distribution Matrix

| Surface | Strongest repo-side artifact today | Current public truth | What still needs to happen | Read-back proof to capture |
| --- | --- | --- | --- | --- |
| **Codex** | `starter-packs/codex/sourceharbor-codex-plugin/` | Codex-compatible plugin bundle exists; official self-serve listing still is not open | use the strongest public distribution surface that Codex currently allows; if an official directory submission path opens, submit there | listing URL, marketplace entry URL, or official directory receipt |
| **Claude Code** | `starter-packs/claude-code/sourceharbor-claude-plugin/` | submission-ready plugin bundle exists; live listing still depends on Anthropic review | submit the bundle to the official marketplace path when account policy and review flow allow it | submission receipt, pending review URL, live listing URL, or review identifier |
| **OpenClaw / ClawHub** | `starter-packs/openclaw/clawhub.package.template.json` plus `starter-packs/openclaw/` | first-cut local starter pack exists; ClawHub package metadata is publish-ready; no live publish receipt exists yet | publish or submit the OpenClaw package to the strongest official surface ClawHub/OpenClaw currently supports | publish receipt, package URL, pending review URL, or registry confirmation |
| **Official MCP Registry** | root `pyproject.toml` + `sourceharbor-mcp` console script + `starter-packs/mcp-registry/sourceharbor-server.template.json` | repo now ships a PyPI-ready install artifact lane; official registry and live PyPI publication still need read-back proof | publish the Python package, then submit or point the MCP Registry entry at the real PyPI artifact | PyPI package URL, registry listing URL, submission receipt, or namespace/publish blocker |
| **Public API image** | `infra/docker/sourceharbor-api.Dockerfile`, `scripts/ci/build_public_api_image.sh`, `.github/workflows/build-public-api-image.yml` | local smoke passed, the image was pushed, and the GHCR package URL now exists at `https://github.com/orgs/xiaojiou176-open/packages/container/package/sourceharbor-api`; anonymous pull is still unauthorized because the package visibility is private | switch the GHCR package visibility to public, then confirm anonymous pull/read-back | GHCR package URL, pushed digest `sha256:62736e47c6fa874d2f21c7f4824ed7ed0cd40df94281c38f772e20ee090ea1fb`, or the exact visibility blocker |
| **Container / Docker runtime infrastructure** | `.devcontainer/**`, `infra/compose/core-services.compose.yml`, `infra/config/strict_ci_contract.json`, `.github/workflows/build-ci-standard-image.yml` | repo ships real local/runtime/CI container assets; the strict CI image stays an infra/proof lane and must not be mistaken for the product image | keep wording scoped to local support, CI parity, and attestation; do not market it as the product install story | current contract digest, attestation artifact, or exact registry blocker |
| **GitHub social preview** | `docs/assets/sourceharbor-social-preview.png` and tracked config entry in `config/public/github-profile.json` | tracked asset exists, but live GitHub upload still remains a manual platform step | upload the image in the GitHub repo social preview settings | live GitHub social preview image shown on the repo |

## Owner-Only Later

These steps usually stay human-only:

- platform login
- marketplace/registry/legal confirmation
- the final publish/submit click
- GitHub social preview upload

## Read-Back Proof

After any submission, capture:

1. submission receipt or success toast
2. pending-review URL or review identifier
3. live listing URL if it already exists
4. exact package / image / bundle version
5. any platform blocker that stopped the flow
