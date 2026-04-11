# Public Distribution Status

Use it like a shipping ledger, not like a launch post.

## Current Public Distribution Matrix

| Surface | Strongest repo-side artifact today | Current public truth | What still needs to happen | Read-back proof to capture |
| --- | --- | --- | --- | --- |
| **Codex** | `starter-packs/codex/sourceharbor-codex-plugin/` | Codex-compatible plugin bundle exists; official self-serve listing still is not open | use the strongest public distribution surface that Codex currently allows; if an official directory submission path opens, submit there | listing URL, marketplace entry URL, or official directory receipt |
| **GitHub Copilot** | `starter-packs/github-copilot/sourceharbor-github-copilot-plugin/` | source-installable GitHub Copilot plugin bundle exists in the repo today | use the docs-supported source-install or repo marketplace path; treat any live marketplace listing as a separate proof layer | source-install read-back, repo marketplace URL, or official listing receipt |
| **Claude Code** | `starter-packs/claude-code/sourceharbor-claude-plugin/` | submission-ready plugin bundle exists; live listing still depends on Anthropic review | submit the bundle to the official marketplace path when account policy and review flow allow it | submission receipt, pending review URL, live listing URL, or review identifier |
| **VS Code agent workflows** | `starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/` | source-installable VS Code agent plugin bundle exists in the repo today | use the docs-supported source-install or plugin-location path; treat any live Marketplace listing as a separate proof layer | source-install read-back, local plugin-location proof, or official listing receipt |
| **OpenClaw / ClawHub** | `starter-packs/openclaw/clawhub.package.template.json` plus `starter-packs/openclaw/` | first-cut local starter pack exists; ClawHub package metadata is publish-ready; no live publish receipt exists yet | publish or submit the OpenClaw package to the strongest official surface ClawHub/OpenClaw currently supports | publish receipt, package URL, pending review URL, or registry confirmation |
| **Official MCP Registry** | root `pyproject.toml` + `sourceharbor-mcp` console script + `starter-packs/mcp-registry/sourceharbor-server.template.json` | repo now ships a PyPI-ready install artifact lane; official registry and live PyPI publication still need read-back proof | publish the Python package, then submit or point the MCP Registry entry at the real PyPI artifact | PyPI package URL, registry listing URL, submission receipt, or namespace/publish blocker |
| **MCP.so** | `config/public/mcp-directory-profile.json` + `docs/submission/mcp-so.md` + `docs/assets/sourceharbor-square-icon.png` | the submit page is reachable, but the current repo-scoped browser session still hits a GitHub OAuth gate first, and the prior real submit attempt produced neither a visible receipt nor an observable request | retry only when you can keep the flow auditable end-to-end, then capture either a real receipt or the exact receiptless stop point | submission receipt, pending-review URL, or a login-gated / no-request blocker note |
| **PulseMCP** | `config/public/mcp-directory-profile.json` + `docs/submission/pulsemcp.md` + `docs/assets/sourceharbor-square-icon.png` | the public submit page currently routes maintainers toward the Official MCP Registry or a manual email path; no stable self-serve server form is exposed in the current read-back | use the registry or editor-managed email path if you want a stronger PulseMCP listing, and record whichever path actually answers | listing URL, acknowledgment email, registry-linked listing, or exact platform blocker |
| **mcpservers.org** | `config/public/mcp-directory-profile.json` + `docs/submission/mcpservers-org.md` + `docs/assets/sourceharbor-square-icon.png` | a submission success receipt already exists; the next proof now depends on review or live listing | wait for approval, then capture the live listing or rejection reason | approval email, live listing URL, or rejection reason |
| **awesome-opencode** | `docs/submission/awesome-opencode.md` | the repo-side listing payload is already upstream as `awesome-opencode/awesome-opencode#270`; the next move depends on maintainer review | wait for review, merge, or rejection and read that result back | PR URL, maintainer feedback, merge URL, or rejection reason |
| **Public API image** | `infra/docker/sourceharbor-api.Dockerfile`, `scripts/ci/build_public_api_image.sh`, `.github/workflows/build-public-api-image.yml` | local smoke passed, the image was pushed, and the product GHCR package `sourceharbor-api` now reads back as `visibility: public`; keep treating it as a separate API-image builder lane, not the default install story | capture anonymous pull/read-back only if you want stronger proof than the GitHub package visibility read-back | GHCR package URL, visibility read-back, anonymous manifest pull, or the exact registry blocker |
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
