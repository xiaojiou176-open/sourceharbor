# Project Status

This page is the shortest truthful answer to:

- what is already real in SourceHarbor
- what is still gated by external dependencies
- what is sample or local-only proof
- what is future direction rather than current capability

Use it like a status board, not like a sales page.

If you need the exhaustive ledger instead of the short board, read
[2026-03-31-program-closeout-matrix.md](./blueprints/2026-03-31-program-closeout-matrix.md).

Release-current truth is a separate ledger from current remote `main`.
Always verify the latest live tag together with the current remote head before
repeating any “release-aligned” claim, because docs/governance closeout commits
can move `main` forward again after a release is cut.

## Current Program State

SourceHarbor is already a real, source-first product-shaped repository.

It has:

- local first-run and doctor flows
- a thin repo-local CLI facade over the existing `bin/*` entrypoints
- a packaged public CLI bridge that delegates into that repo-local substrate
- a first public TypeScript SDK over the HTTP contract
- public compatibility docs, starter prompts, and examples for Codex / Claude Code builders, plus a first-cut OpenClaw local pack
- plugin-grade Codex and Claude Code bundles
- ClawHub package metadata and official MCP Registry metadata templates
- Search, story-aware briefing-backed Ask, shared-story Briefings, MCP, and Ops front doors
- a reader frontstage with published reader documents, navigation brief, yellow-warning honesty, and source contribution drawer
- strong-supported YouTube/Bilibili intake plus generalized RSSHub/RSS source intake templates
- watchlists, merged stories, trends, briefings, bundles, and a sample playground
- proof and runtime-truth surfaces that explain where confidence comes from

What it does **not** have today:

- a hosted workspace promise
- autopilot product claims
- live external notification proof without sender configuration
- universal no-secret proof for Gemini-backed lanes
- route-by-route verification across the full RSSHub universe

## Release-Current Truth

Treat release-current truth as its own ledger.

Current live reading:

- the public repo has a live GitHub Release object
- the latest live release is currently `v0.1.24`, and the latest live read-back
  shows it aligned with the current remote `main` head again
- workflow-dispatch evidence on current `main` is still its own ledger, but the
  current head now also has fresh successful runs for release evidence
  attestation, the public API image lane, and the strict CI standard-image lane

Practical implication:

- release-current proof now exists for the current canonical public repo, and
  the latest live read-back currently says the release and remote `main` are
  aligned again
- release-current wording must stay honest the next time current `main` moves
  ahead again after the tag cut
- older tag-era wording should stay historical, not be reused as if it were the
  current release
- if `main` moves again after this point, re-check whether release-current truth
  still matches the remote head before repeating release-aligned claims

## Release And Public Distribution Truth

The public repo now has strong current-`main` proof, but release-current truth
and official-surface distribution truth are still separate ledgers.

- current `main` is active and externally verifiable through GitHub checks and
  fresh workflow-dispatch lanes
- the public distribution artifacts are real, but several official-surface submissions still need true submit/read-back proof
- the current public repo has a live GitHub Release object that currently matches
  the latest remote `main` read-back
- official-surface listing truth is still separate from GitHub Release truth

Use:

- [public-distribution.md](./public-distribution.md) for Codex / Claude Code / OpenClaw / MCP Registry submission truth
- [proof.md](./proof.md) for release-vs-remote-vs-local proof boundaries

## Verified And Ready

These are the strongest current claims:

- **First-run base path:** `./bin/bootstrap-full-stack`, `./bin/full-stack up`, `./bin/doctor`, and the runtime route snapshot under `.runtime-cache/run/full-stack/resolved.env`
- **CLI surfaces:** existing `bin/*` entrypoints remain the repo-local command truth, while `packages/sourceharbor-cli` adds a thin installable bridge for public discovery and starter flows
- **Public TypeScript SDK:** `packages/sourceharbor-sdk` now exposes a thin contract-first SDK over the same HTTP contract and shared route semantics
- **Public starter surface:** `starter-packs/` is the public entry directory, while `docs/public-skills.md`, `docs/compat/*`, `templates/public-skills/*`, and `examples/*` act as companion first-cut starter assets without exposing internal `.agents/skills`
- **Local write-route contract:** direct write APIs can be exercised with the local dev token path instead of pretending auth is an unresolved product gap
- **Source intake contract:** strong-supported YouTube/Bilibili templates plus generalized RSSHub/RSS substrate without overclaiming full-universe proof, with the `/subscriptions` front door now consuming the same template catalog exposed through API and MCP
- **Reader pipeline:** `ClusterVerdictManifest`, `PublishedReaderDocument`, `CoverageLedger`, `TraceabilityPack`, `repair` modes, and `NavigationBrief` now exist as repo-side runtime surfaces over `ConsumptionBatch`
- **Feed-to-reader bridge:** `/feed` remains the digest/job reading lane, but digest items can now surface the current published reader document route when a current reader edition already exists for that source item
- **Front doors:** `/reader`, `/search`, `/ask` (story-aware, briefing-backed answer/change/evidence flow with truthful raw-retrieval fallback, selected-story drill-down, and a server-owned story page payload that now reuses one canonical selected-story object from Briefings), `/briefings` (server-owned briefing page payload for selected story, compare route, and Ask handoff), `/mcp`, `/ops`, `/subscriptions`
- **Compounder layer:** `/watchlists`, `/trends` (merged stories + recent evidence), `/briefings` (summary -> differences -> evidence for one watchlist, now with one shared selected-story payload that carries forward into Ask), `/playground`, and `GET /api/v1/jobs/{job_id}/bundle`
- **Reader API + MCP surface:** `/api/v1/reader/*` plus reader MCP tools for document listing, detail, and navigation brief
- **Truth surfaces:** [proof.md](./proof.md), [runtime-truth.md](./runtime-truth.md), [start-here.md](./start-here.md), [testing.md](./testing.md)

## Public Face And Distribution Readiness

These are the strongest outward-facing artifacts that already exist today:

- tracked GitHub description, homepage, topics, and Discussions intent through
  [`config/public/github-profile.json`](../config/public/github-profile.json)
- a tracked social-preview upload asset path:
  `docs/assets/sourceharbor-social-preview.png`
- a tracked public asset pack and media-kit doc: [media-kit.md](./media-kit.md)
- plugin-grade Codex and Claude Code bundles
- first-cut OpenClaw pack plus ClawHub metadata template
- official MCP Registry metadata template

What is still missing for a stronger public-ready claim:

- live GitHub social preview upload in repo settings
- real official-surface submission receipts or pending-review links for Claude,
  OpenClaw / ClawHub, and the official MCP Registry path
- a truthful strongest-public-surface proof path for Codex while official
  self-serve listing remains unavailable

## Implemented But Still Gated

These surfaces are real, but their strongest proof still depends on external conditions:

| Surface | Current truth | Gate |
| --- | --- | --- |
| Notifications / reports | implemented routes and settings exist | verified sender configuration, especially `RESEND_FROM_EMAIL`, plus a target mailbox |
| UI audit Gemini review | base audit is real and a recent maintainer-local proof pass exercised the Gemini review layer | other environments still need Gemini access if they want the review layer |
| Computer use | contract and service exist, and a recent maintainer-local proof pass reached the provider | valid Gemini access, supported account capability, and a real screenshot/input contract |
| Long live smoke | repo path exists, the repo-managed `bootstrap -> up -> status -> doctor` path was re-proven again, the short smoke path now passes locally, and YouTube provider validation removed the stale-key `403` story as the main blocker | the full end-to-end live receipt still depends on operator-managed API access plus the intentionally deferred Resend sender-identity lane |

## Site Capability Truth

These are the durable site-level capability boundaries worth remembering.

| Site | Current repo role | Strongest layer today | Gate / boundary | Verdict |
| --- | --- | --- | --- | --- |
| Google Account | local browser-proof anchor for login persistence and repo-owned Chrome sanity checks | DOM / page-state proof only | local login state when you intentionally run real-profile proof | **already-covered** |
| YouTube | strong-supported source plus local live browser proof target | hybrid: Data API + DOM / page-state proof | shared operator key persistence and local login state when strict live proof is reopened | **already-covered** |
| Bilibili account center | local account-proof anchor for the strong-supported Bilibili source lane | DOM today, hybrid later if stronger account-side automation is justified | human login in the repo-owned Chrome profile | **external-blocked** |
| Resend dashboard | operator-side notification and sender-identity proof surface, not a content-ingestion source | admin UI + provider configuration | human login plus `RESEND_FROM_EMAIL` / sender-domain setup | **external-blocked** |
| RSSHub / RSS sources | generalized source-universe intake substrate | HTTP / API, not browser-first | source availability and route/feed correctness, not browser login | **already-covered** |

If you want the more exact "what can still be deepened safely" ledger, read
[site-capability.md](./site-capability.md).

## Sample And Local-Proof Boundaries

These are intentionally **not** live hosted proof:

- [samples/README.md](./samples/README.md)
- `/playground`
- seeded local watchlist / trend / bundle proofs used for seeded local validation

Safe interpretation:

- they prove the product shape and local runtime path
- they do **not** prove remote production traffic, hosted delivery, or current release distribution

## Future Directions, Not Current Capability

Two directions remain explicitly in the bet bucket:

| Direction | Current decision |
| --- | --- |
| Agent Autopilot / advanced agent workflows | human-in-the-loop spike is worth considering; product claim is not |
| Hosted / managed workspace | no-go for current positioning; only a small hosted-shaped evaluation slice is worth reconsidering later |

Read the spike artifacts:

- [Program Closeout Matrix](./blueprints/2026-03-31-program-closeout-matrix.md)
- [Agent Autopilot Spike](./blueprints/2026-03-31-agent-autopilot-spike.md)
- [Hosted Readiness Spike](./blueprints/2026-03-31-hosted-readiness-spike.md)
- [Ecosystem And Big-Bet Decisions](./reference/ecosystem-and-big-bet-decisions.md)

## Ecosystem And Big-Bet Buckets

This is the short scoreboard for the directions most likely to get overstated.

| Track | Current bucket | Why now |
| --- | --- | --- |
| Codex / GitHub Copilot / Claude Code / VS Code agent workflows via MCP + HTTP API | **ship-now** | the repo already has real MCP, API, search, ask, and job-trace surfaces |
| Repo-local CLI/help facade | **ship-now** | `./bin/sourceharbor` is already a truthful discoverability layer over `bin/*` |
| Packaged public CLI bridge | **ship-now** | `packages/sourceharbor-cli` is now the installable public bridge, while the fuller repo-local operator CLI remains `./bin/sourceharbor` |
| Public TypeScript SDK | **ship-now** | `packages/sourceharbor-sdk` now exposes the contract-first builder layer over the existing HTTP contract |
| Codex-compatible plugin bundle | **ship-now** | `starter-packs/codex/sourceharbor-codex-plugin/` is now the strongest public Codex bundle the repo can ship before official self-serve listing exists |
| GitHub Copilot plugin bundle | **ship-now** | `starter-packs/github-copilot/sourceharbor-github-copilot-plugin/` now gives GitHub Copilot a real source-installable plugin bundle over the same MCP/API truth |
| Claude Code plugin bundle | **ship-now** | `starter-packs/claude-code/sourceharbor-claude-plugin/` is now the strongest public submission-ready bundle for Claude Code |
| VS Code agent plugin bundle | **ship-now** | `starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/` now gives VS Code agent workflows a real source-installable plugin bundle over the same MCP/API truth |
| OpenClaw via local starter pack + MCP / HTTP substrate | **first-cut** | the repo ships a compatibility page plus a first-cut local OpenClaw starter pack, but it still is not a marketplace or primary front-door claim |
| OpenClaw ClawHub package template | **first-cut** | the repo ships a publish-ready metadata template, but there is still no live ClawHub publish receipt and `CLAWHUB_TOKEN` is currently unset locally |
| Official MCP Registry listing + metadata template | **ship-now** | the registry now has a live active `SourceHarbor MCP` entry; the remaining work is version refresh, not first publication |
| Site-specific MCP directory packets | **first-cut** | `config/public/mcp-directory-profile.json` plus `docs/submission/*.md` give the repo a real per-directory packet layer, but same-day submit/read-back still varies per site |
| Public Python SDK | **later** | no public package surface exists yet |
| Public skills pack / templates | **first-cut** | `docs/public-skills.md`, `docs/compat/*`, `templates/public-skills/*`, and `examples/*` now provide a usable first public starter surface, but not a fully hardened ecosystem product yet |
| Plugin / extension marketplace as the primary product identity | **no-go now** | plugin-first positioning would still overstate the current repo truth even after the new bundle/template surfaces landed |
| Agent Autopilot (approval-first research ops) | **spike-only** | only the approval-first research-ops slice is worth reopening |
| Full autonomous autopilot | **no-go now** | approval, rollback, identity, and provider readiness are not strong enough |
| Thin managed evaluation slice | **later** | only a narrow managed bridge is worth reconsidering after current proof boundaries stay intact |
| Full hosted workspace | **no-go now** | multi-tenant auth, custody, isolation, and support contracts are not ready |
| Growth / moat thesis | **ship-now** | the current moat is the proof-first control tower story plus reusable compounder surfaces, not hosted scale or plugin sprawl |

## External Blockers

These are the genuine external or human-only dependencies still left after the
current maintainer re-audit:

- Resend live delivery still needs a real sender identity chain: `RESEND_FROM_EMAIL`, a verified sender/domain, and a destination mailbox
- the strict YouTube live-smoke lane now has recent local proof, but the full lane still needs operator-managed YouTube API access when it is reopened
- official-surface public distribution is now split more sharply:
  - Official MCP Registry is already live, but still lagging the newest repo snapshot
  - `awesome-opencode` is submitted and waiting on maintainer review
  - `mcpservers.org` and `MCP.so` still need same-day public read-back proof
  - ClawHub still needs a real publish step and auth
- the GitHub social preview image still remains a manual platform upload step even though the tracked asset chain already exists

Raw non-empty values for `YOUTUBE_API_KEY`, `RESEND_API_KEY`, and
`GEMINI_API_KEY` are no longer the main blocker story. The remaining blockers
are more specific than generic "secret missing" language.

### Exact External Action Pack

| Blocker | Freshly verified state | Why this is external/human-only | Exact action |
| --- | --- | --- | --- |
| Resend sender identity | provider canary still reports `config_error`; sender configuration remains incomplete because `RESEND_FROM_EMAIL` is still missing | repo code already exposes notifications and settings; GitHub/release truth is no longer the missing piece | set `RESEND_FROM_EMAIL`, verify the sender/domain in Resend, choose a real destination mailbox, then rerun the provider canary or strict live-smoke lane |
| YouTube strict live-smoke | recent local proof now passes direct probe, provider canary, and strict live-smoke preflight; the remaining step is restoring operator-managed YouTube API access whenever the full live lane is reopened | repo-side implementation is no longer the blocker; the remaining action is making the intended YouTube API access available when the lane is rerun | restore the intended YouTube API access in the environment used for the live-smoke lane, then rerun the strict live-smoke lane when you want the full end-to-end receipt |
| Official MCP Registry version refresh | the registry currently lists an active `SourceHarbor MCP` entry at public version `0.1.14`, while the repo-controlled package and directory packet have already moved ahead to `0.1.19` | the repo already has the package, template, and listing truth; the missing step is a deliberate publish/refresh action with package credentials plus a fresh registry read-back | publish the intended current package version when the right credentials are available, then read the updated version back from the official registry |
| GitHub social preview | the tracked asset already exists in-repo, but live upload/read-back still remains a manual GitHub Settings step | the remaining step is a manual upload in GitHub repo settings, not a repo-code change | upload `docs/assets/sourceharbor-social-preview.png` in GitHub repo social preview settings, then read the live setting back |

## Remote Truth Reading Rules

Fresh GitHub-side verification must be rerun against the current remote head
whenever `main` moves again. The safe reading rules are:

- treat current `main`, latest release, and workflow-dispatch evidence as separate ledgers
- only treat GitHub checks and workflow-dispatch runs as current remote proof when their recorded `headSha` still matches the current remote head
- workflow-dispatch lanes such as standard-image publish or release attestation may require repo-scope environment approval, and their readiness receipts can be green even when the current head still has no remote run receipt yet
- latest-release truth must still be checked live against the current remote `main`, because post-release docs/governance closeouts can move `main` ahead again before the next tag is cut
- live GitHub description, homepage, topics, and discussions should be checked live against `config/public/github-profile.json` before repeating the claim
- live provider proof still stays a separate ledger from GitHub/release proof

## Read Next

- [README.md](../README.md)
- [start-here.md](./start-here.md)
- [proof.md](./proof.md)
- [runtime-truth.md](./runtime-truth.md)
- [testing.md](./testing.md)
