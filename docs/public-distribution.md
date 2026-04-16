# Public Distribution Status

Use it like a shipping ledger, not like a launch post.

## Public ledger scope

This page only reports distribution-level proof: what is already published, what awaits credentials, and which owner-manual actions remain. It does not expose internal blueprint or execution ledgers; those stay in the maintainer-only planning ledger. Link to this page whenever you mention official distribution claims so readers see the exact ledger and blocking steps.

## Current Public Distribution Matrix

| Surface | Strongest repo-side artifact today | Current public truth | What still needs to happen | Read-back proof to capture |
| --- | --- | --- | --- | --- |
| **Codex** | `starter-packs/codex/sourceharbor-codex-plugin/` | Codex-compatible plugin bundle exists; official self-serve listing still is not open | use the strongest public distribution surface that Codex currently allows; if an official directory submission path opens, submit there | listing URL, marketplace entry URL, or official directory receipt |
| **GitHub Copilot** | `starter-packs/github-copilot/sourceharbor-github-copilot-plugin/` | source-installable GitHub Copilot plugin bundle exists in the repo today | use the docs-supported source-install or repo marketplace path; treat any live marketplace listing as a separate proof layer | source-install read-back, repo marketplace URL, or official listing receipt |
| **Claude Code** | `starter-packs/claude-code/sourceharbor-claude-plugin/` | submission-ready plugin bundle exists; live listing still depends on Anthropic review | submit the bundle to the official marketplace path when account policy and review flow allow it | submission receipt, pending review URL, live listing URL, or review identifier |
| **VS Code agent workflows** | `starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/` | source-installable VS Code agent plugin bundle exists in the repo today | use the docs-supported source-install or plugin-location path; treat any live Marketplace listing as a separate proof layer | source-install read-back, local plugin-location proof, or official listing receipt |
| **OpenClaw / ClawHub** | `starter-packs/openclaw/clawhub.package.template.json` plus `starter-packs/openclaw/` | first-cut local starter pack exists and the repo still ships a publish-shaped ClawHub metadata template, but there is still no public ClawHub package receipt and the local shell still has no `CLAWHUB_TOKEN` | publish through the strongest current OpenClaw / ClawHub path (`clawhub package publish <source>`) only when auth is available, then capture the real receipt | publish receipt, package URL, pending review URL, registry confirmation, or auth blocker |
| **Official MCP Registry** | root `pyproject.toml` + `sourceharbor-mcp` console script + `starter-packs/mcp-registry/sourceharbor-server.template.json` + `.github/workflows/publish-mcp-registry.yml` | **fresh anonymous registry read-back confirms a live active entry** for `io.github.xiaojiou176-open/sourceharbor-mcp` at public version `0.1.14`, while the repo-tracked package and directory packet sit at `0.1.19`; the latest refresh attempt failed early because the workflow first verifies that live PyPI already serves `sourceharbor==0.1.19`, and today that prerequisite still fails | wait until live PyPI serves `sourceharbor==0.1.19`, then rerun `publish-mcp-registry.yml` and capture the refreshed listing/API read-back before repeating a newer snapshot claim | registry listing URL/API read-back, published package version, or exact blocker (`live PyPI version 0.1.14 does not match expected_version 0.1.19`) |
| **PyPI (`sourceharbor`)** | root `pyproject.toml` + `sourceharbor-mcp` console script + `.github/workflows/publish-pypi.yml` | **fresh JSON read-back confirms a live PyPI project** at version `0.1.14`; the repo-controlled package version is still `0.1.19`, and the latest publish attempt reached the real publish step and failed with exact blocker `invalid-publisher` for environment `external-pypi-publish` | configure the PyPI-side Trusted Publisher for project `sourceharbor`, repository `xiaojiou176-open/SourceHarbor`, workflow file `.github/workflows/publish-pypi.yml`, and protected environment `external-pypi-publish`; then rerun `publish-pypi.yml` and read the new version back from PyPI | package URL/API read-back, published package version, or exact blocker (`invalid-publisher`) |
| **MCP.so** | `config/public/mcp-directory-profile.json` + `docs/media-kit.md` + `docs/assets/sourceharbor-square-icon.png` | the repo-side listing inputs are ready, but a fresh anonymous direct read-back at `/server/sourceharbor-mcp` currently returns **`Project not found`**; there is still no public live listing proof on that route today | retry only when you can keep the flow auditable end-to-end, then capture either a real receipt or the exact receiptless stop point | submission receipt, pending-review URL, live listing URL, or the exact `Project not found` blocker |
| **PulseMCP** | `config/public/mcp-directory-profile.json` + `docs/media-kit.md` + `docs/assets/sourceharbor-square-icon.png` | a fresh anonymous public page read-back now shows a live `SourceHarbor` server page plus a visible `server.json` link; this surface no longer needs to be treated as blocked | keep the listing read-back URL as proof and only revisit it if the page disappears or diverges from the repo-managed packet | live listing URL, `server.json` URL, or later drift note |
| **mcpservers.org** | `config/public/mcp-directory-profile.json` + `docs/media-kit.md` + `docs/assets/sourceharbor-square-icon.png` | fresh anonymous direct/search read-back still does **not** prove a live listing for `sourceharbor`; direct requests currently return `404 Not Found`, so public listing truth remains unproven | wait for approval or publication, then capture the live listing or rejection reason | approval email, live listing URL, or a fresh search/direct-read blocker note |
| **awesome-opencode** | `docs/builders.md` + `docs/public-distribution.md` | the repo-side listing payload is upstream as `awesome-opencode/awesome-opencode#270`, and a fresh GitHub read-back still shows that PR open | wait for review, merge, or rejection and read that result back | PR URL, maintainer feedback, merge URL, or exact blocker reason |
| **Public API image** | `infra/docker/sourceharbor-api.Dockerfile`, `scripts/ci/build_public_api_image.sh`, `.github/workflows/build-public-api-image.yml` | local smoke passed, the image was pushed, the product GHCR package `sourceharbor-api` reads back as `visibility: public`, and release-aligned publish receipts already exist; current-head workflow-dispatch proof still needs a fresh reread for each new head before it is treated as current proof | capture anonymous pull/read-back only if you want stronger proof than the GitHub package visibility read-back plus the latest publish receipt | GHCR package URL, visibility read-back, anonymous manifest pull, or the exact registry blocker |
| **Container / Docker runtime infrastructure** | `.devcontainer/**`, `infra/compose/core-services.compose.yml`, `infra/config/strict_ci_contract.json`, `.github/workflows/build-ci-standard-image.yml` | repo ships real local/runtime/CI container assets; the strict CI image stays an infra/proof lane and must not be mistaken for the product image; release-aligned publish + attestation receipts already exist, but current-head workflow-dispatch proof still needs a fresh reread for each new head before it is treated as current proof | keep wording scoped to local support, CI parity, reviewed promotion, and attestation; do not market it as the product install story | current contract digest, attestation artifact, or exact registry blocker |
| **GitHub social preview** | `docs/assets/sourceharbor-social-preview.png` and tracked config entry in `config/public/github-profile.json` | tracked asset exists, but live GitHub upload still remains a manual platform step; the repo currently treats the tracked asset as preparation only, not as proof that the live setting has already been uploaded | upload the image in the GitHub repo social preview settings, then read the live setting back manually | live GitHub social preview image shown on the repo |

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
