# Public Distribution Status

Use it like a shipping ledger, not like a launch post.

## Current Public Distribution Matrix

| Surface | Strongest repo-side artifact today | Current public truth | What still needs to happen | Read-back proof to capture |
| --- | --- | --- | --- | --- |
| **Codex** | `starter-packs/codex/sourceharbor-codex-plugin/` | Codex-compatible plugin bundle exists; official self-serve listing still is not open | use the strongest public distribution surface that Codex currently allows; if an official directory submission path opens, submit there | listing URL, marketplace entry URL, or official directory receipt |
| **GitHub Copilot** | `starter-packs/github-copilot/sourceharbor-github-copilot-plugin/` | source-installable GitHub Copilot plugin bundle exists in the repo today | use the docs-supported source-install or repo marketplace path; treat any live marketplace listing as a separate proof layer | source-install read-back, repo marketplace URL, or official listing receipt |
| **Claude Code** | `starter-packs/claude-code/sourceharbor-claude-plugin/` | submission-ready plugin bundle exists; live listing still depends on Anthropic review | submit the bundle to the official marketplace path when account policy and review flow allow it | submission receipt, pending review URL, live listing URL, or review identifier |
| **VS Code agent workflows** | `starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/` | source-installable VS Code agent plugin bundle exists in the repo today | use the docs-supported source-install or plugin-location path; treat any live Marketplace listing as a separate proof layer | source-install read-back, local plugin-location proof, or official listing receipt |
| **OpenClaw / ClawHub** | `starter-packs/openclaw/clawhub.package.template.json` plus `starter-packs/openclaw/` | first-cut local starter pack exists; the repo also ships a publish-shaped ClawHub metadata template, but there is still no live ClawHub package read-back and `CLAWHUB_TOKEN` is currently unset in the local shell | publish through the strongest current OpenClaw / ClawHub path (`clawhub package publish <source>`) only when auth is available, then capture the real receipt | publish receipt, package URL, pending review URL, registry confirmation, or auth blocker |
| **Official MCP Registry** | root `pyproject.toml` + `sourceharbor-mcp` console script + `starter-packs/mcp-registry/sourceharbor-server.template.json` | **live listing now exists**: the official registry currently returns `io.github.xiaojiou176-open/sourceharbor-mcp` as an active entry, but the public package snapshot is still `0.1.14`, so this lane is now about version-refresh truth instead of first publication | refresh the published package / registry snapshot when publish credentials are intentionally available, then read the new version back from the registry | registry listing URL/API read-back, published package version, or namespace/publish blocker |
| **MCP.so** | `config/public/mcp-directory-profile.json` + `docs/submission/mcp-so.md` + `docs/assets/sourceharbor-square-icon.png` | the repo-side packet is ready, but same-day public listing and same-day submission receipt still were not observable in the current verification pass; the submit page is real and currently fronted by sign-in | retry only when you can keep the flow auditable end-to-end, then capture either a real receipt or the exact receiptless stop point | submission receipt, pending-review URL, or a login-gated / no-request blocker note |
| **PulseMCP** | `config/public/mcp-directory-profile.json` + `docs/submission/pulsemcp.md` + `docs/assets/sourceharbor-square-icon.png` | the public path currently behaves more like a platform-managed downstream of the Official MCP Registry plus a manual editor/contact path; same-day public listing for SourceHarbor still was not visible | use the registry-linked or editor-managed route only when you want a stronger listing, and capture the exact path that answered | listing URL, acknowledgment email, registry-linked listing, or exact platform blocker |
| **mcpservers.org** | `config/public/mcp-directory-profile.json` + `docs/submission/mcpservers-org.md` + `docs/assets/sourceharbor-square-icon.png` | the repo-side packet remains valid, but same-day public listing still was not read back; the current truth is “submitted / waiting for review or publication”, not “already live” | wait for approval or publication, then capture the live listing or rejection reason | approval email, live listing URL, or rejection reason |
| **awesome-opencode** | `docs/submission/awesome-opencode.md` | the repo-side listing payload is already upstream as `awesome-opencode/awesome-opencode#270`; the next move depends on maintainer review | wait for review, merge, or rejection and read that result back | PR URL, maintainer feedback, merge URL, or rejection reason |
| **Public API image** | `infra/docker/sourceharbor-api.Dockerfile`, `scripts/ci/build_public_api_image.sh`, `.github/workflows/build-public-api-image.yml` | local smoke passed, the image was pushed, and the product GHCR package `sourceharbor-api` now reads back as `visibility: public`; keep treating it as a separate API-image builder lane, not the default install story | capture anonymous pull/read-back only if you want stronger proof than the GitHub package visibility read-back | GHCR package URL, visibility read-back, anonymous manifest pull, or the exact registry blocker |
| **Container / Docker runtime infrastructure** | `.devcontainer/**`, `infra/compose/core-services.compose.yml`, `infra/config/strict_ci_contract.json`, `.github/workflows/build-ci-standard-image.yml` | repo ships real local/runtime/CI container assets; the strict CI image stays an infra/proof lane and must not be mistaken for the product image | keep wording scoped to local support, CI parity, and attestation; do not market it as the product install story | current contract digest, attestation artifact, or exact registry blocker |
| **GitHub social preview** | `docs/assets/sourceharbor-social-preview.png` and tracked config entry in `config/public/github-profile.json` | tracked asset exists, but live GitHub upload still remains a manual platform step; current GitHub read-back still reports `usesCustomOpenGraphImage=false` | upload the image in the GitHub repo social preview settings | live GitHub social preview image shown on the repo |

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
