# SourceHarbor

<p align="center">
  <img
    src="./docs/assets/sourceharbor-studio-preview.svg"
    alt="SourceHarbor studio preview showing the reader, timeline, and proof surfaces"
    width="100%"
  />
</p>

<p align="center">
  <strong>Read long-form sources first. Open proof, search, and builder tools only when you need them.</strong>
</p>

<p align="center">
  <a href="./docs/see-it-fast.md">See It Fast</a>
  ·
  <a href="./docs/start-here.md">Run Locally</a>
</p>

<p align="center">
  <img alt="CI" src="https://github.com/xiaojiou176-open/SourceHarbor/actions/workflows/ci.yml/badge.svg" />
  <img alt="License" src="https://img.shields.io/github/license/xiaojiou176-open/SourceHarbor" />
  <img alt="GitHub Discussions" src="https://img.shields.io/github/discussions/xiaojiou176-open/SourceHarbor" />
  <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/xiaojiou176-open/SourceHarbor?style=social" />
</p>

SourceHarbor helps you turn long-form sources into a reader-first flow of
grounded search results, finished reading surfaces, and inspectable job runs.
It stays source-first and proof-first: you can inspect it, run it locally, and
verify each surface instead of trusting product copy on vibes alone.

> **Current reading specimen**
>
> `Bilibili history milestone: the earliest surviving AV2.`
>
> One readable title up front. One short excerpt. Proof one click away.

## Start With One First Path

Choose one first move:

| If you want to... | Open this first | Why this is the right first door |
| --- | --- | --- |
| **See the product first** | [docs/see-it-fast.md](./docs/see-it-fast.md), then [docs/proof.md](./docs/proof.md) | start with the reader and the evidence before you boot anything |
| **Run one real local flow** | [docs/start-here.md](./docs/start-here.md) | this is the shortest truthful path from clone to `/reader`, `/feed`, `/search`, `/ask`, and one real job |

If you are here as a builder, skip straight to [docs/builders.md](./docs/builders.md) and [docs/public-distribution.md](./docs/public-distribution.md) after you understand the reader-first front door.

If you only remember one sentence, remember this:

> SourceHarbor is a **reader-first, source-first, proof-first** product repo.

Current intake truth:

- **strong support:** YouTube channels and Bilibili creators
- **general substrate:** RSSHub routes and generic RSS/Atom feeds
- **not yet claimable:** route-by-route verification for the full RSSHub universe

## Product In One Glance

| Surface | Why open it first | Current truth |
| --- | --- | --- |
| **Reader** | See the finished surface instead of starting in a control panel | real local route after boot: `/reader` |
| **Subscriptions + Feed** | Follow a few sources, then watch the reading flow fill in | real local routes after boot: `/subscriptions` and `/feed` |
| **Search + Ask** | Search saved material or ask for the current story with evidence nearby | real local routes after boot: `/search` and `/ask` |
| **Jobs + Proof** | Inspect the pipeline, artifacts, and truth layers instead of trusting marketing copy | `/jobs`, [docs/proof.md](./docs/proof.md), and [docs/project-status.md](./docs/project-status.md) |

SourceHarbor is a **multi-surface product repo, not a single skill package**.
Public starter packs and plugin-grade bundles are adoption layers inside that
repo. They are not the whole product, and they are not raw exports of the
internal `.agents/skills` tree.

## What It Does Not Claim Today

Think of this as the label on the box, not fine print:

- SourceHarbor is **not** presented as a hosted SaaS or online signup product.
- Agent Autopilot is **not** a shipped capability; it remains a bounded spike direction.
- Hosted Team Workspace is **not** a current promise; it remains a deferred bet.
- SourceHarbor does **not** yet ship a public Python SDK.
- SourceHarbor does **not** claim that one public image is the whole product stack; the dedicated API image still expects external Postgres/Temporal once you move past health-only smoke.
- SourceHarbor does **not** collapse a repo-side PyPI/GHCR route into a live registry claim without read-back proof.
- SourceHarbor does **not** claim official marketplace or registry listing everywhere.
- SourceHarbor does **not** yet claim a registry-published OpenClaw plugin package or official Codex directory listing.
- SourceHarbor does **not** claim that every RSSHub route has already been individually validated.

If you need the explicit bet boundaries, read:

- [Ecosystem And Big-Bet Decisions](./docs/reference/ecosystem-and-big-bet-decisions.md)
- [Future-direction boundaries](./docs/reference/project-positioning.md)

## Public Readiness Notes

Keep these truth layers separate when you read or share the repo:

- current `main` truth can move ahead of the latest release tag
- tracked GitHub profile metadata can move ahead of the live GitHub repo settings
- workflow-dispatch lanes such as release evidence attestation and strict CI standard-image publish are manual proof lanes, not the public install ledger, even when required checks on `main` are already green
- local support-service containers plus devcontainer/strict-CI images do not turn Docker or GHCR into the current product front door
- local real-profile browser proof can confirm login persistence and page state without turning those same sites into source-ingestion product claims

That is why SourceHarbor keeps `proof.md`, `project-status.md`, and the public-reference docs as separate ledgers instead of one blanket “ready” claim.

## Compounder Layer

These are the surfaces that make SourceHarbor reusable instead of one-and-done:

| Compounder | What it does | Current truth |
| --- | --- | --- |
| **Watchlists** | Save a topic, claim kind, or source matcher as a durable tracking object | Real route: `/watchlists` |
| **Trends** | Compare recent matched runs for a watchlist and show what was added or removed | Real route: `/trends` |
| **Briefings** | Collapse one watchlist into a unified story surface that starts with the current summary, highlights recent deltas, and keeps evidence one click away | Real route: `/briefings`; now backed by a server-owned briefing page payload that shares one canonical selected-story object with Ask |
| **Evidence bundle** | Export one job as a reusable internal bundle with digest, trace summary, knowledge cards, and artifact manifest | Real route on demand: `/api/v1/jobs/<job-id>/bundle` |
| **Playground** | Explore clearly labeled sample corpus and demo outputs without pretending they are live operator state | Real route: `/playground` + [docs/samples/README.md](./docs/samples/README.md) |
| **Use-case pages** | Route newcomer traffic into truthful capability stories for YouTube, Bilibili, RSS, MCP, and research workflows | Real routes: `/use-cases/youtube`, `/use-cases/bilibili`, `/use-cases/rss`, `/use-cases/mcp-use-cases`, `/use-cases/research-pipeline` |

## Future Directions Under Evaluation

These are real directions, but they are **not** current product claims:

- **Agent Autopilot** is currently a spike topic, not a shipped capability. The most honest next slice is human-approved workflow orchestration, not silent autonomy. See [docs/reference/project-positioning.md](./docs/reference/project-positioning.md).
- **Hosted or managed SourceHarbor** is also a spike topic, not a current promise. Today the repository remains source-first and local-proof-first. See [docs/reference/project-positioning.md](./docs/reference/project-positioning.md).

## See It In 30 Seconds

If you only have half a minute, do not start with setup.

Start with three surfaces:

1. **Reader:** the finished reading surface.
2. **Digest feed:** the reading desk that keeps one item in focus.
3. **Job trace:** the evidence view behind each result.

```text
Source -> queued job -> timeline -> reader / proof -> MCP / API reuse
```

## Why Star SourceHarbor Now

- **It solves the full loop, not a single step.** SourceHarbor handles subscription intake, ingestion, digest production, artifact indexing, retrieval, and notification-ready outbound lanes in one system.
- **It exposes proof, not vague claims.** Jobs, artifacts, step summaries, CI, and local verification paths are all first-class public surfaces.
- **It is ready for operators and agents at the same time.** Humans use the reader-facing web surfaces. Agents use API and MCP. Both point at the same pipeline.
- **It is already shaped like a real product.** The repository is source-first and inspectable, but the public surface is now optimized around outcomes rather than internal wiring.

## What You Get

| Surface | What you can do | Why it matters |
| :-- | :-- | :-- |
| **Subscriptions** | Start from strong YouTube/Bilibili templates or widen into RSSHub and generic RSS intake through the shared backend template catalog | Build a durable intake layer without pretending every source family is equally proven |
| **Timeline** | Read generated summaries in one calm flow, then jump into the current reader edition when a story is ready | Turn long-form content into an actionable daily reading stream without hiding the finished published-doc layer |
| **Search & Ask** | Search raw evidence and turn a watchlist or selected story briefing into an answer + change + citation flow on one page, with Briefings and Ask now sharing a server-owned story read-model instead of parallel browser-side selection glue | Make the knowledge layer visible without pretending every question already has a global answer engine |
| **Job trace** | Inspect pipeline status, retries, degradations, and artifacts | Debug with evidence instead of guessing what happened |
| **Notifications** | Configure and send digests outward when the notification lane is enabled | Push results outward instead of trapping them in a database |
| **Retrieval** | Search over generated artifacts | Reuse digests as a searchable knowledge layer |
| **MCP tools** | Expose subscriptions, ingestion, jobs, artifacts, search, and notifications to agents | Let assistants act on the same system without custom glue code |

## Run Locally: Result Path

README is no longer the full operator walkthrough.

Use it to choose the next page, then leave quickly:

- **No-boot tour:** [docs/see-it-fast.md](./docs/see-it-fast.md)
- **First real local run:** [docs/start-here.md](./docs/start-here.md)
- **Runtime and verification truth:** [docs/proof.md](./docs/proof.md), [docs/testing.md](./docs/testing.md), [docs/runtime-truth.md](./docs/runtime-truth.md)
- **Builder/package surfaces:** [docs/builders.md](./docs/builders.md), [packages/sourceharbor-cli/README.md](./packages/sourceharbor-cli/README.md), [packages/sourceharbor-sdk/README.md](./packages/sourceharbor-sdk/README.md)

If you need the live operator-side log trail after a local run, start at
`.runtime-cache/logs/components/full-stack`.

## Builder Off-Ramp

If you are here as a builder, use the builder path on purpose:

- **MCP / API / CLI / SDK map:** [docs/builders.md](./docs/builders.md)
- **Official submit/read-back truth:** [docs/public-distribution.md](./docs/public-distribution.md)
- **Public packages and starter packs:** [`packages/sourceharbor-cli`](./packages/sourceharbor-cli/README.md), [`packages/sourceharbor-sdk`](./packages/sourceharbor-sdk/README.md), [`starter-packs/README.md`](./starter-packs/README.md)
- **Registry ownership marker:** `mcp-name: io.github.xiaojiou176-open/sourceharbor-mcp`

Container truth also stays separate on purpose:

- the repo newcomer path is still [docs/start-here.md](./docs/start-here.md)
- the dedicated API image is a builder lane, not the default install story
- core-services compose, devcontainer, and strict-CI images are runtime or infrastructure surfaces, not the product front door

## Why SourceHarbor Feels Different

Most repos in this space stop at one of these layers:

- a transcript extractor
- a summarizer script
- a search index
- an internal operations surface

SourceHarbor is built around the full knowledge flow:

1. **Capture** sources continuously
2. **Process** each item into job-backed artifacts
3. **Read** results in the timeline and finished reader
4. **Search** generated knowledge later
5. **Deliver** updates through configured notifications when the outbound lane is enabled
6. **Reuse** the same surface through MCP and API

See the full comparison in [docs/compare.md](./docs/compare.md).

## Public Proof, Not Hand-Waving

This repository does not ask you to trust product copy on its own.

- **Proof of behavior:** [docs/start-here.md](./docs/start-here.md)
- **Proof of runtime truth:** [docs/runtime-truth.md](./docs/runtime-truth.md)
- **Proof of architecture:** [docs/architecture.md](./docs/architecture.md)
- **Proof of verification:** [docs/testing.md](./docs/testing.md)
- **Proof of current public claims:** [docs/proof.md](./docs/proof.md)

GitHub profile intent is tracked in `config/public/github-profile.json`. Use
`python3 scripts/github/apply_public_profile.py --verify` to compare the live
description, homepage, and topics against the current tracked intent, and use
`python3 scripts/github/apply_public_profile.py` when you intentionally want to
sync those settings after current `main` truth is ready. Social preview upload
still requires a manual GitHub Settings check.

Operator-generated pointers and historical planning ledgers can help maintainers inspect deeper evidence, but they are not the public truth route.

> SourceHarbor is a public, source-first engineering repository.
>
> It is inspectable, and you can run it locally. It is not marketed as a turnkey hosted product, and external distribution claims are valid only when live remote workflows prove them for the current `main` commit.

For local verification, the repo-managed route snapshot under
`.runtime-cache/run/full-stack/resolved.env` is the runtime truth for API/Web
ports. Do not assume any process already listening on `9000`, `3000`, or
`5432` belongs to the clean-path stack.

## Documentation Map

Start where you are:

- **I want the fastest first impression:** [docs/index.md](./docs/index.md)
- **I want the no-boot product tour:** [docs/see-it-fast.md](./docs/see-it-fast.md)
- **I want to see a real local result:** [docs/start-here.md](./docs/start-here.md)
- **I want the system map:** [docs/architecture.md](./docs/architecture.md)
- **I want the MCP quickstart:** [docs/mcp-quickstart.md](./docs/mcp-quickstart.md)
- **I want the public builder packages:** [docs/builders.md](./docs/builders.md), [starter-packs/README.md](./starter-packs/README.md), [packages/sourceharbor-cli/README.md](./packages/sourceharbor-cli/README.md), [packages/sourceharbor-sdk/README.md](./packages/sourceharbor-sdk/README.md)
- **I want proof and verification commands:** [docs/proof.md](./docs/proof.md)
- **I want testing and CI details:** [docs/testing.md](./docs/testing.md)
- **I want positioning and trade-offs:** [docs/compare.md](./docs/compare.md)
- **I want contributor/community paths:** [CONTRIBUTING.md](./CONTRIBUTING.md), [SUPPORT.md](./SUPPORT.md), [SECURITY.md](./SECURITY.md)

## FAQ Snapshot

### Is this a hosted SaaS?

No. SourceHarbor is a source-first repository you can inspect, run locally, adapt, and extend.

### Is this only for video?

No. The public surface is strongest around long-form video today, but the feed and retrieval layers already model both `video` and `article` content types.

### Why star it if I am not deploying it this week?

Because it sits at the intersection of source ingestion, digest pipelines, retrieval, operator UI, and MCP reuse. Even if you are not adopting it immediately, it is a strong reference point for how to turn long-form inputs into reusable knowledge products.

More questions are answered in [docs/faq.md](./docs/faq.md).

## Repository Surfaces

- `apps/api`: FastAPI service for ingestion, jobs, artifacts, retrieval, notifications, and operator controls
- `apps/worker`: pipeline runner, Temporal workflows, and delivery automation
- `apps/mcp`: MCP tool surface for agents
- `apps/web`: reader-first web surfaces for operators and builders
- `contracts`: shared schemas and generated contract artifacts
- `docs`: layered public navigation, proof, and architecture

## Community

- **Questions and roadmap discussion:** [GitHub Discussions](https://github.com/xiaojiou176-open/SourceHarbor/discussions)
- **Bug reports and feature requests:** [GitHub Issues](https://github.com/xiaojiou176-open/SourceHarbor/issues)
- **Security reports:** [SECURITY.md](./SECURITY.md)
- **Project conduct and ownership:** [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md), [.github/CODEOWNERS](./.github/CODEOWNERS)
- **Rights and public artifact boundaries:** [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md), [docs/reference/public-artifact-exposure.md](./docs/reference/public-artifact-exposure.md)
- **Public asset provenance:** [docs/reference/public-assets-provenance.md](./docs/reference/public-assets-provenance.md)

## License

SourceHarbor is released under the MIT License. See [LICENSE](./LICENSE).
