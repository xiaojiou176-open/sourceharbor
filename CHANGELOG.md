# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows semantic-ish release communication even when the repository is still evolving.

## [Unreleased]

## [0.1.18] - 2026-04-10

### Added

- added a truthful `/reader/demo` preview detail route so the reader detail frontstage can be inspected before the first live document lands

### Changed

- deepened the reader frontstage hierarchy so `/reader` behaves more like an editorial reading desk and less like a dashboard shell
- refined the reader detail layout, yellow-warning contract, and evidence drawer copy so body-first reading stays primary while backstage proof remains on demand
- tightened loading-state semantics and refreshed the public version anchors to `0.1.18` so current `main` and the next release can stay aligned

## [0.1.17] - 2026-04-10

### Added

- added source-installable GitHub Copilot and VS Code agent plugin bundles under `starter-packs/`
- added public compatibility docs and prompt templates for GitHub Copilot and VS Code agent workflows
- added a canonical MCP directory profile plus site-specific submission packets for `MCP.so`, `PulseMCP`, and `mcpservers.org`
- added a tracked `awesome-opencode` listing packet and a square icon source asset for directory submissions

### Changed

- bumped the root Python package, public CLI, public TypeScript SDK, starter-pack manifests, and plugin bundle version anchors to `0.1.17`
- aligned outward-facing version anchors across `contracts/source/openapi.yaml`, `apps/api/app/config.py`, `infra/docker/sourceharbor-api.Dockerfile`, and `uv.lock`
- tightened the public distribution docs so GitHub Copilot / VS Code agent bundles now read as real repo-tracked surfaces instead of future repack work

## [0.1.14] - 2026-04-08

### Changed

- clarified the container/distribution truth split so local compose, devcontainer parity, and the GHCR strict CI image no longer read like one public Docker install story
- clarified that SourceHarbor is a multi-surface product repo and that skill-package criteria apply only to its public starter-pack and plugin-grade distribution surfaces
- bumped the public CLI, public TypeScript SDK, OpenAPI contract, and plugin/template version anchors to `0.1.14` so the latest release line catches back up with the current `main` head after the distribution-truth closeout landed

## [0.1.13] - 2026-04-07

### Fixed

- aligned the packaged CLI fallback docs URL with the live GitHub Pages front door instead of the raw GitHub docs tree
- bumped the public CLI, public TypeScript SDK, OpenAPI contract, and plugin/template version anchors to `0.1.13` so the next release can catch back up with current `main`

## [0.1.12] - 2026-04-06

### Changed

- transferred the canonical public repository into the `xiaojiou176-open` organization while keeping the public `sourceharbor` entry and `main` branch intact
- rewired public-facing GitHub URLs, metadata defaults, GHCR references, and registry templates to the canonical `xiaojiou176-open/sourceharbor` slug
- tightened workflow security guardrails with `zizmor`, `trivy`, and `trufflehog`, then aligned the main GitHub Actions lanes so the canonical org repo is fresh-green again

## [0.1.11] - 2026-04-04

### Fixed

- marked the tracked `v0.1.10` release manifest as a historical example so it no longer reads like fresh current-run evidence after being committed into the repository
- clarified the comparison and front-door quickstart wording so provider-gated notification delivery no longer reads like unconditional live proof
- aligned public runtime examples with the real repo-managed contract by using `SOURCE_HARBOR_API_BASE_URL` / `API_PORT` instead of the stale `SOURCE_HARBOR_API_PORT` wording
- refreshed stale external-lane blocker wording after the current-main protected lanes succeeded

### Changed

- updated MCP quickstart and public examples to prefer `resolved.env` / `SOURCE_HARBOR_API_BASE_URL` / `API_PORT` instead of hardcoding `127.0.0.1:9000`
- aligned package README install examples with the current repo-truth path: install from a checkout first, then swap to a published package name only after registry publication is real
- renamed the public starter-pack story to “first-cut public starter surface” so the entry directory, compatibility docs, template assets, and examples read like one honest layer instead of a fully hardened ecosystem product
- bumped the public CLI, public TypeScript SDK, and OpenAPI contract version anchors to `0.1.11` so the latest release line can catch back up with current `main`

## [0.1.10] - 2026-04-04

### Fixed

- tolerated duplicate coverage-path rewrites during strict python coverage normalization so the repo-side strict lane no longer fails after the test suite itself has already passed

## [0.1.9] - 2026-04-04

### Fixed

- restored the tracked `v0.1.7` release manifest to the historical-example contract, including `git.dirty=true`, so it no longer reads like current clean proof
- restored the release-manifest capture script to the current-run contract so fresh release evidence generation stays aligned with the supply-chain contract tests

### Changed

- bumped the public CLI, public TypeScript SDK, and OpenAPI contract version anchors to `0.1.9` so the latest release line can stay aligned after the release-manifest governance fix

## [0.1.8] - 2026-04-04

### Fixed

- made the tracked release manifest contract honest by marking tracked release manifests as historical examples instead of current-run proof

### Changed

- bumped the public CLI, public TypeScript SDK, and OpenAPI contract version anchors to `0.1.8` so the latest release line can stay aligned after the release-manifest governance fix

## [0.1.7] - 2026-04-04

### Fixed

- isolated the ops inbox route tests behind an explicit route dependency so full strict python verification no longer depends on global app-state patching
- clarified the runtime-truth wording so the docs no longer claim the latest release and current `main` are the same commit when they are not

### Changed

- bumped the public CLI, public TypeScript SDK, and OpenAPI contract version anchors to `0.1.7` so the latest release line can catch back up with the current `main` head
- clarified that the public starter-pack / public skills surface is available today but still first-cut, so builder docs do not overstate ecosystem maturity

## [0.1.6] - 2026-04-04

### Changed

- promoted disk governance into a more resilient Ops / doctor hardening gate, including safer fallback behavior when audit policy or report data is unreadable
- clarified the public starter surface so `starter-packs/` stays the public entry directory and `templates/public-skills/**` stays the copyable template asset layer
- clarified the repo-local CLI wording so `./bin/sourceharbor` no longer reads like the repository has no packaged public CLI
- bumped the public CLI, public TypeScript SDK, and OpenAPI contract version anchors to `0.1.6` so the next release line matches the current `main` head

## [0.1.5] - 2026-04-03

### Fixed

- aligned the public SDK/web URL helper boundary so the extracted SDK keeps the same route-building contract the web shell expects
- bumped the public CLI and TypeScript SDK package versions to `0.1.5` so the next release line matches the current patch-release head

## [0.1.4] - 2026-04-03

### Added

- first public builder packages under `packages/sourceharbor-cli` and `packages/sourceharbor-sdk`
- first public compatibility docs and starter packs for Codex / Claude Code under `docs/compat/*`, `docs/public-skills.md`, and `templates/public-skills/**`
- first public builder examples under `examples/cli` and `examples/sdk`

### Changed

- upgraded the builder story from repo-local-only CLI substrate to a split model: repo-local operator CLI plus thin public CLI and TypeScript SDK
- refreshed README, builders, project-status, proof, compare, start-here, see-it-fast, docs index, and GitHub profile intent to match the new thin public surfaces
- narrowed the YouTube external blocker wording from a generic hard `403` claim to a verified provider-configuration result plus a remaining secure credential-provisioning action

## [0.1.3] - 2026-04-03

### Changed

- tightened the durable ecosystem decision ledger so Switchyard stays explicitly out of the current cycle, alongside the existing no-go or later buckets for packaged CLI, public SDK, public Skills, and plugin-market positioning
- refreshed the README non-promises so the public front door stays aligned with the shipped repo-local CLI surface, current builder-facing truth, and the still-deferred ecosystem bets
- refreshed project-status and proof so protected-lane and release-current wording no longer stays pinned to an older pre-closeout world
- fail-closed stale upstream compat rows so aged provider receipts no longer present themselves as current verification
- registered the ecosystem decision ledger in the docs governance control plane
- marked the tracked `v0.1.2` release manifest as a historical example to match the release-artifact governance rules

## [0.1.2] - 2026-04-03

### Added

- first-run doctor and operator diagnostics surfaces for local runtime truth
- watchlists and cross-run trend pages for persistent tracking
- job evidence bundle export for internal reuse and async collaboration
- read-only sample corpus and playground surfaces
- truthful use-case landing pages for YouTube, Bilibili, RSS, MCP, and research pipeline discovery
- a thin `./bin/sourceharbor` facade that exposes the existing repo-owned `bin/*` entrypoints as one discoverable local CLI/help surface

### Changed

- docs governance now treats `pre-commit` as a first-class required check and stops misreading workflow event rows as branch-protection checks
- hosted GHCR publish lanes now prefer the repository-scoped `GITHUB_TOKEN` path for login and SBOM registry auth in current workspace fixes
- release evidence readiness now fail-closes on rollback gate drift, invalid rollback drill evidence, and failing required prechecks instead of checking file presence alone
- rollback guidance now documents the destructive `content_type` down migration path as schema-restoring rather than lossless
- builder docs now separate the truthful repo-local CLI substrate from the future packaged CLI / SDK path
- README, start-here, and MCP quickstart now expose the repo-local command surface without overclaiming a packaged public CLI

## [0.1.1] - 2026-03-26

### Added

- a result-first README that sells outcomes before governance
- layered docs entrypoints for start-here, proof, comparison, and FAQ
- public visual assets for hero, architecture, and social preview
- a GitHub profile manifest and apply script for description, topics, and discussions
- a release note categorization file for sustainable public release communication
- a no-boot product tour page for newcomers who want to evaluate the repo before setup

### Changed

- public quickstart now follows a result path instead of an installation-only path
- public proof is now treated as a dedicated evidence layer instead of being implied by test directories
- docs navigation now favors newcomer flow over deep governance-first reading
- README first screen now leads with visible result surfaces instead of a concept-only product story
