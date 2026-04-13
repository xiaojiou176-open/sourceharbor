# SourceHarbor

<p align="center">
  <img
    src="./docs/assets/sourceharbor-studio-preview.svg"
    alt="SourceHarbor studio preview showing source intake, digest generation, and searchable artifacts"
    width="100%"
  />
</p>

<p align="center">
  <img
    src="./docs/assets/sourceharbor-hero.svg"
    alt="SourceHarbor preview showing the command center, digest feed, and job trace surfaces a newcomer will inspect first."
    width="100%"
  />
</p>

<p align="center">
  <strong>Proof-first AI knowledge control tower for source intake, grounded search, and agent workflows, with one shared Web/API/MCP truth and strong YouTube/Bilibili lanes.</strong>
</p>

<p align="center">
  <a href="#see-it-in-30-seconds">See It In 30 Seconds</a>
  ·
  <a href="./docs/start-here.md">Run Locally</a>
  ·
  <a href="./docs/see-it-fast.md">No-Boot Tour</a>
  ·
  <a href="./docs/index.md">Docs Home</a>
  ·
  <a href="./docs/mcp-quickstart.md">MCP Quickstart</a>
  ·
  <a href="./docs/builders.md">Builders</a>
  ·
  <a href="./docs/public-distribution.md">Distribution Status</a>
  ·
  <a href="./starter-packs/README.md">Starter Packs</a>
  ·
  <a href="./docs/media-kit.md">Media Kit</a>
  ·
  <a href="./docs/samples/README.md">Sample Corpus</a>
  ·
  <a href="./docs/proof.md">Proof</a>
  ·
  <a href="./docs/project-status.md">Project Status</a>
  ·
  <a href="./docs/compare.md">Why It Stands Out</a>
  ·
  <a href="https://github.com/xiaojiou176-open/sourceharbor/discussions">Discussions</a>
</p>

<p align="center">
  <img alt="CI" src="https://github.com/xiaojiou176-open/sourceharbor/actions/workflows/ci.yml/badge.svg" />
  <img alt="License" src="https://img.shields.io/github/license/xiaojiou176-open/sourceharbor" />
  <img alt="GitHub Discussions" src="https://img.shields.io/github/discussions/xiaojiou176-open/sourceharbor" />
  <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/xiaojiou176-open/sourceharbor?style=social" />
</p>

SourceHarbor helps you turn long-form sources into grounded search results,
knowledge cards, traceable job runs, and MCP-ready operations. It stays
source-first and proof-first: you can inspect it, run it locally, and verify
each surface instead of trusting product copy on vibes alone.

Three quick reasons developers keep reading:

- **One truth across Web, API, and MCP.** Operators and agent builders see the same jobs, artifacts, and retrieval state instead of three disconnected product shells.
- **Proof sits next to the product story.** The README, proof ladder, runtime truth, and job receipts all point at the same contract, so the repo earns trust instead of asking for it.
- **Strong lanes plus honest boundaries.** YouTube and Bilibili are the rich lanes today, RSSHub and generic RSS widen the source universe, and the docs say plainly where route-by-route proof still stops.

Two repo-managed runtime details matter when you verify changes locally:

- the web app runs from the repo-owned runtime workspace under
  `.runtime-cache/tmp/web-runtime/workspace/apps/web`
- repo-side strict CI reads the current-commit mutation receipt from
  `.runtime-cache/reports/mutation/mutmut-cicd-stats.json` when that artifact
  already exists and matches the current HEAD

The honest intake boundary today is:

- **strong support:** YouTube channels and Bilibili creators
- **general support:** RSSHub routes and generic RSS/Atom feeds
- **not yet claimable:** route-by-route verification for the full RSSHub universe

That intake split now lives behind one shared template catalog instead of
separate Web-only presets: the `/subscriptions` front door, HTTP API, and MCP
surface all point at the same strong-supported vs generalized intake contract.

It is strongest when you read it as a control tower for source intake:

- operators use the Web command center
- system builders use the HTTP API
- Codex, GitHub Copilot, Claude Code, VS Code agent workflows, and other MCP-aware clients use the MCP surface
- all of them point at the same jobs, artifacts, retrieval index, and operator truth

SourceHarbor is a **multi-surface product repo, not a single skill package**.
Public starter packs and plugin-grade skill surfaces are adoption layers inside
that repo. They are not the whole product, and they are not raw exports of the
internal `.agents/skills` tree.

<p align="center">
  <img
    src="./docs/assets/sourceharbor-developer-flywheel.svg"
    alt="SourceHarbor developer flywheel showing sources, job trace, knowledge cards, grounded search, MCP and API reuse, and the operator loop."
    width="100%"
  />
</p>

## Why Developers Lean In

This is the part that makes SourceHarbor more than a pretty README:

| If you are... | What pulls you in | Why it feels different |
| --- | --- | --- |
| **A builder chasing Codex / GitHub Copilot / Claude Code / VS Code agent workflows** | one repo already exposes MCP, HTTP API, and a shared operator truth | you do not have to invent a fake assistant shell just to reach real jobs, artifacts, and retrieval |
| **An operator who cares about proof** | job trace, ops inbox, watchlists, trends, and bundle exports all point back to the same pipeline | the repo keeps receipts, not just summaries |
| **A maintainer deciding whether to contribute** | the product story, runtime truth, and testing story now line up | you can tell what is real, what is gated, and what is still a deliberate bet without re-reading the whole archive |

The hook is simple:

- **Search** gives the evidence surface.
- **Subscriptions** gives the source-universe intake front door.
- **Ask** gives the story-aware, briefing-backed answer/change/evidence front door, now pushed toward a server-owned page payload instead of a front-end stitched view model.
- **MCP** gives Codex / GitHub Copilot / Claude Code / VS Code agent / builder reuse.
- **Watchlists + Trends + Playground** make the system worth coming back to instead of treating it like a one-shot summarizer.

## Choose Your First Path

You do not need every door on day one.

Pick the first path that matches why you are here:

| If you want to... | Open this first | Why this is the right first door |
| --- | --- | --- |
| **See whether the product is real** | [docs/see-it-fast.md](./docs/see-it-fast.md), then [docs/proof.md](./docs/proof.md) | start with the shop window, then inspect the proof ladder before you commit to a longer run |
| **Read the merged reader product directly** | `/reader` after local boot, then [docs/start-here.md](./docs/start-here.md) | this is the shortest truthful path to the new published-doc layer, navigation brief, yellow warning surface, and source contribution drawer |
| **Run SourceHarbor as an operator** | [docs/start-here.md](./docs/start-here.md), then `/subscriptions`, `/feed`, `/search`, and `/ops` after local boot | this is the shortest truthful path from clone to source-universe intake, identity-first reading flow, evidence, and triage |
| **Build on top of SourceHarbor** | [docs/builders.md](./docs/builders.md), [docs/mcp-quickstart.md](./docs/mcp-quickstart.md), and [docs/public-distribution.md](./docs/public-distribution.md) | these pages separate MCP, API, CLI, SDK, starter packs, and official-surface submission truth without mixing them into the newcomer path |

## Front Doors

The fastest way to understand the product is to open the highest-value rooms first:

| Front door | What it means | Current truth |
| --- | --- | --- |
| **Reader** | Published-doc frontstage over frozen consumption batches, where merge docs and singleton polish docs share one reading surface with navigation brief, yellow warning, and source contribution drawer | Real Web route after local boot: `/reader`; current repo truth is local-first and repo-side proven, not hosted-distribution proof |
| **Subscriptions** | Source-universe intake front door with one shared template catalog, tracked-universe atlas, and manual-intake workbench for strong-supported YouTube/Bilibili lanes, generalized RSSHub/RSS intake, and one-off video/article URLs that can enter today without becoming subscriptions first | Real Web route after local boot: `/subscriptions` + shared catalog through API and MCP |
| **Search** | Operator-facing evidence search over digests, knowledge cards, transcripts, and related artifacts | Real Web route after local boot: `/search` |
| **Ask your sources** | Story-aware, briefing-backed Ask front door: with watchlist and story context it returns the current answer, recent changes, and citation drill-down through a server-owned page payload; without context it falls back to grounded retrieval | Real Web route after local boot: `/ask` + [grounded contract](./docs/blueprints/2026-03-31-ask-your-sources-grounded-answer-contract.md) |
| **Briefings** | Lowest-cognitive-load unified story view for one watchlist: summary first, then differences, then evidence drill-down, with one canonical selected-story page payload that Ask reuses instead of parallel browser-side aliases | Real Web route after local boot: `/briefings`; grounded in watchlists, merged stories, jobs, and knowledge |
| **Watchlists** | Durable tracking object surface for saved topics, claim kinds, platform slices, and source matchers | Real Web route after local boot: `/watchlists` |
| **Trends** | Compounder front door that turns repeated watchlist hits into merged stories plus recent evidence runs | Real Web route after local boot: `/trends` |
| **MCP** | Agent-facing surface on top of the same API and pipeline state | [docs/mcp-quickstart.md](./docs/mcp-quickstart.md) + `./bin/dev-mcp` |
| **Ops / doctor** | First-run diagnosis, operator triage, and next-step guidance for runtime truth, failed jobs, ingest issues, and live-hardening gates | `./bin/doctor` + `/ops` after local boot + [docs/runtime-truth.md](./docs/runtime-truth.md) |
| **Playground** | Clearly labeled sample-proof lane for demo corpus, example jobs, retrieval results, and use-case navigation without pretending to be live operator truth | Real Web route after local boot: `/playground` + [docs/samples/README.md](./docs/samples/README.md) |

## Builder Entry Points

SourceHarbor is not just a Web app. It already has multiple access layers for builders and agent workflows:

The builder-facing mental map should follow the same product line:

- `/subscriptions` establishes the intake contract
- `/watchlists` stores the tracking object
- `/trends` turns repeated runs into the compounder front door
- `/briefings` and `/ask` share the story-aware page payload
- `/mcp` reuses that same system truth for agents

| Entry point | Who it is for | Current truth |
| --- | --- | --- |
| **Codex / GitHub Copilot / Claude Code / VS Code agent workflows** | local operators who want an AI coding or operations agent to query and drive the same system truth | honest fit today through MCP + HTTP API, documented in [docs/builders.md](./docs/builders.md) |
| **OpenClaw workflows** | builders who want a dedicated OpenClaw first hop instead of only generic MCP theory | first-cut fit today through [docs/compat/openclaw.md](./docs/compat/openclaw.md) plus [starter-packs/openclaw/README.md](./starter-packs/openclaw/README.md) |
| **Plugin-grade bundles and official-surface templates** | builders who want the strongest public bundles or distribution templates beyond docs-only starters | real today through `starter-packs/codex/sourceharbor-codex-plugin/`, `starter-packs/github-copilot/sourceharbor-github-copilot-plugin/`, `starter-packs/claude-code/sourceharbor-claude-plugin/`, `starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/`, `starter-packs/openclaw/clawhub.package.template.json`, `starter-packs/mcp-registry/sourceharbor-server.template.json`, and `config/public/mcp-directory-profile.json`; readiness differs by platform |
| **Packaged public CLI** | builders who want an installable command surface before memorizing repo entrypoints | real today in [`packages/sourceharbor-cli`](./packages/sourceharbor-cli/README.md); it stays thinner than the repo-local runtime CLI and delegates inside a checkout |
| **Repo-local CLI substrate** | operators already inside a checkout who want the direct runtime and governance command truth | real today via `./bin/sourceharbor help`, which remains the underlying local command truth |
| **MCP surface** | agent workflows and assistant clients that need governed access to jobs, artifacts, retrieval, ingest, reports, and notifications | real surface today via [`./bin/dev-mcp`](./docs/mcp-quickstart.md) |
| **HTTP API contract** | product builders, automation, and SDK consumers | real contract today via [`contracts/source/openapi.yaml`](./contracts/source/openapi.yaml) |
| **Public TypeScript SDK** | TypeScript builders who want a thin client over the same HTTP contract | real today in [`packages/sourceharbor-sdk`](./packages/sourceharbor-sdk/README.md); it stays contract-first and builder-facing |
| **Public starter packs** | builders who want reproducible Codex / GitHub Copilot / Claude Code / VS Code agent / OpenClaw / SDK starting templates | available today as a first-cut surface in [`starter-packs/`](./starter-packs/README.md); these are public templates, starter skills, and compatibility notes, not raw internal `.agents/skills` exports |

The packaging story is intentionally thin: the packaged CLI stays repo-aware and
delegates to `./bin/sourceharbor` inside a checkout, the TypeScript SDK stays a
contract-first wrapper over the HTTP API, and Python SDK support still stays
later.

Skill-repo criteria apply only **partially** here:

| Surface | Skill-repo criteria apply? | Why |
| --- | --- | --- |
| **Whole SourceHarbor repo** | No | this repo ships Web, API, MCP, runtime, and builder layers together; it is a multi-surface product repo |
| **`starter-packs/**`** | Yes, mostly | these are newcomer-facing starter surfaces with copyable prompts, templates, and clear adoption paths |
| **plugin-grade bundle directories** | Yes, strongly | these are the closest repo-owned artifacts to official marketplace or registry submission |
| **internal `.agents/skills/**`** | No public applicability | they stay internal operating aids, not newcomer-facing exports |

Plugin-grade distribution is now one layer stronger than raw docs:

- Codex has a plugin-shaped bundle for repo or personal marketplace distribution, but official Codex directory self-serve publishing is still not open.
- GitHub Copilot now has a source-installable plugin bundle, but any official marketplace or directory listing is still a separate proof layer.
- Claude Code has a submission-ready plugin bundle, but official listing still depends on Anthropic review.
- VS Code agent workflows now have a source-installable plugin bundle, but a live Marketplace listing is still a separate proof layer.
- OpenClaw has a first-cut local starter pack plus a publish-ready ClawHub package template, but not a live ClawHub publish receipt.
- MCP now has a real Python package lane plus the official-registry-shaped template; live registry or PyPI read-back still requires submit/publish proof.

If you want the shortest truthful answer to "what already exists vs what still
needs official submit/read-back proof," open
[docs/public-distribution.md](./docs/public-distribution.md).

## Public Packages Now

These packages are the public box around the same repo-owned logic:

- **CLI:** install [`packages/sourceharbor-cli`](./packages/sourceharbor-cli/README.md) when you want one thin command surface for the repo-local command substrate.
- **TypeScript SDK:** install [`packages/sourceharbor-sdk`](./packages/sourceharbor-sdk/README.md) when you want a typed HTTP client instead of inventing a second fetch stack.
- **MCP server package:** build the root Python package when you want the real `sourceharbor-mcp` console script and the PyPI-shaped install artifact that the MCP Registry template now targets.
- **Starter packs:** open [`starter-packs/README.md`](./starter-packs/README.md) when you want reproducible Codex / GitHub Copilot / Claude Code / VS Code agent / OpenClaw / SDK starting templates rather than raw internal skill files; this surface is available today, but it is still first-cut.

Registry ownership marker:

`mcp-name: io.github.xiaojiou176-open/sourceharbor-mcp`

## Container Truth Split

Do not read every container-shaped artifact in this repo as a newcomer-facing
product container.

| Container surface | What it is for | Current truth |
| --- | --- | --- |
| **`infra/compose/core-services.compose.yml`** | repo-local core services for Postgres and Temporal | local operator/runtime helper for SourceHarbor boot; not a public product container distribution |
| **`.devcontainer/devcontainer.json` + `.devcontainer/Dockerfile`** | contributor workspace parity | local development environment for people working inside a checkout; not a packaged newcomer product artifact |
| **`infra/docker/sourceharbor-api.Dockerfile` + `ghcr.io/xiaojiou176-open/sourceharbor-api`** | dedicated product API image route | builder-facing API container lane; the GHCR package now reads back as `visibility: public`, but it still is a separate API-image builder surface rather than the default install story |
| **`infra/config/strict_ci_contract.json` + `ghcr.io/xiaojiou176-open/sourceharbor-ci-standard`** | strict CI and devcontainer parity image | infrastructure image for CI, attestation, and repeatable tooling; **not** newcomer-facing product container distribution |

So the honest newcomer path stays:

- run the repo from [`docs/start-here.md`](./docs/start-here.md)
- use the packaged CLI / SDK / starter packs when you want public builder surfaces
- use the dedicated API image only when you explicitly want the API container lane
- do **not** treat the strict CI GHCR image as the product's install story

Minimal examples:

```bash
npm install --global ./packages/sourceharbor-cli
cd /path/to/sourceharbor
sourceharbor help

npm install ./packages/sourceharbor-sdk

uv build
```

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
- [Agent Autopilot Spike](./docs/blueprints/2026-03-31-agent-autopilot-spike.md)
- [Hosted Readiness Spike](./docs/blueprints/2026-03-31-hosted-readiness-spike.md)

## Public Readiness Notes

Keep these truth layers separate when you read or share the repo:

- current `main` truth can move ahead of the latest release tag
- tracked GitHub profile metadata can move ahead of the live GitHub repo settings
- workflow-dispatch lanes such as release evidence attestation and strict CI standard-image publish are manual proof lanes, not the public install ledger, even when required checks on `main` are already green
- local support-service containers plus devcontainer/strict-CI images do not turn Docker or GHCR into the current product front door
- local real-profile browser proof can confirm login persistence and page state without turning those same sites into source-ingestion product claims

That is why SourceHarbor keeps `proof.md`, `project-status.md`, `runbook-local.md`, and the public-reference docs as separate ledgers instead of one blanket “ready” claim.

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

- **Agent Autopilot** is currently a spike topic, not a shipped capability. The most honest next slice is human-approved workflow orchestration, not silent autonomy. See [docs/blueprints/2026-03-31-agent-autopilot-spike.md](./docs/blueprints/2026-03-31-agent-autopilot-spike.md).
- **Hosted or managed SourceHarbor** is also a spike topic, not a current promise. Today the repository remains source-first and local-proof-first. See [docs/blueprints/2026-03-31-hosted-readiness-spike.md](./docs/blueprints/2026-03-31-hosted-readiness-spike.md).

## First Practical Win

Choose the shortest honest path for the result you want first:

| I want to... | Do this first | What I get |
| --- | --- | --- |
| discover the repo-local command surface first | `./bin/sourceharbor help` | a thin menu over the existing `bin/*` entrypoints without inventing a second CLI stack |
| evaluate without booting anything | [docs/see-it-fast.md](./docs/see-it-fast.md) | the fastest public tour of the command center, digest feed, and job trace |
| run a real local flow | [docs/start-here.md](./docs/start-here.md) | the shortest repo-documented path to a local stack and a queued or completed job |
| inspect the trust boundary first | [docs/proof.md](./docs/proof.md) | the current proof map, including what is locally provable and where the public boundary stops |

There are three honest first paths:

- **Evaluate fast:** inspect the product shape and evidence surfaces without booting anything.
- **Run locally:** install dependencies, boot the stack, and queue a real job on your own machine.
- **Inspect the trust boundary:** read the proof ladder first so you know exactly which claims are local proof and which still depend on live remote verification.

> Truth route, in plain English:
> `README.md` is the front door, [`docs/start-here.md`](./docs/start-here.md) is the first real run, [`docs/proof.md`](./docs/proof.md) is the proof ladder, `docs/generated/*` pages are render-only pointers, and `.agents/Plans/*` files are historical execution archives rather than current public truth.

Current non-promises:

- SourceHarbor is **not** described here as a turnkey hosted team workspace.
- Agent autopilot remains a bounded spike direction, not a shipped product capability.
- Those future-direction boundaries live in [docs/reference/project-positioning.md](./docs/reference/project-positioning.md), [docs/reference/ecosystem-and-big-bet-decisions.md](./docs/reference/ecosystem-and-big-bet-decisions.md), and the Prompt 5 spike blueprints under [docs/blueprints/](./docs/blueprints/).

If you want the shortest honest summary of what is already real, what is still gated, and what remains future direction, read [docs/project-status.md](./docs/project-status.md).

## See It In 30 Seconds

If you only have half a minute, do not start with setup. Start with the three surfaces that explain the product fastest:

1. **Command center:** one operator view for subscriptions, intake, job counts, and recent artifacts.
2. **Digest feed:** a reading flow where entries such as `AI Weekly` and `Digest One` become reusable summaries instead of lost links, and already-materialized items can jump straight into the current reader edition.
3. **Job trace:** a step-by-step timeline with statuses, retries, degradations, and artifact references.

```text
Source -> queued job -> digest feed -> searchable artifact -> MCP / API reuse
```

Representative result shape, based on the current digest template and UI surfaces:

```markdown
# AI Weekly

> Source: [Original video](https://www.youtube.com/watch?v=abc)
> Platform: youtube | Video ID: video-uid-123 | Generated at: 2026-02-10T00:00:00Z

## One-Minute Summary
- This episode focuses on agent workflows, operator visibility, and job trace.

## Key Takeaways
- Every job carries a step summary, artifacts index, and pipeline final status.
```

For the lightweight evaluation path, go to [docs/see-it-fast.md](./docs/see-it-fast.md).

## Why Star SourceHarbor Now

- **It solves the full loop, not a single step.** SourceHarbor handles subscription intake, ingestion, digest production, artifact indexing, retrieval, and notification-ready outbound lanes in one system.
- **It exposes proof, not vague claims.** Jobs, artifacts, step summaries, CI, and local verification paths are all first-class public surfaces.
- **It is ready for operators and agents at the same time.** Humans use the command center. Agents use API and MCP. Both point at the same pipeline.
- **It is already shaped like a real product.** The repository is source-first and inspectable, but the public surface is now optimized around outcomes rather than internal wiring.

## What You Get

| Surface | What you can do | Why it matters |
| :-- | :-- | :-- |
| **Subscriptions** | Start from strong YouTube/Bilibili templates or widen into RSSHub and generic RSS intake through the shared backend template catalog | Build a durable intake layer without pretending every source family is equally proven |
| **Digest feed** | Read generated summaries in one operator flow, then jump into the current reader edition when that digest already has a published doc bridge | Turn long-form content into an actionable daily reading stream without hiding the finished published-doc layer |
| **Search & Ask** | Search raw evidence and turn a watchlist or selected story briefing into an answer + change + citation flow on one page, with Briefings and Ask now sharing a server-owned story read-model instead of parallel browser-side selection glue | Make the knowledge layer visible without pretending every question already has a global answer engine |
| **Job trace** | Inspect pipeline status, retries, degradations, and artifacts | Debug with evidence instead of guessing what happened |
| **Notifications** | Configure and send digests outward when the notification lane is enabled | Push results outward instead of trapping them in a database |
| **Retrieval** | Search over generated artifacts | Reuse digests as a searchable knowledge layer |
| **MCP tools** | Expose subscriptions, ingestion, jobs, artifacts, search, and notifications to agents | Let assistants act on the same system without custom glue code |

## Evaluate Fast: No-Boot Tour

Think of this like walking past a storefront window before deciding whether to step inside.

This path is for evaluation, not a hosted trial. You are inspecting the product shape, evidence surfaces, and result format before deciding whether a local run is worth it.

1. Open [docs/see-it-fast.md](./docs/see-it-fast.md) to see the command center, digest feed, and job trace path in one page.
2. Open [docs/proof.md](./docs/proof.md) to see what is locally provable today and where the public-proof boundary stops. Treat it as the evidence map, not as a machine-generated live verdict page.
3. If the shape matches what you need, continue to [docs/start-here.md](./docs/start-here.md) for the local boot path.

## Run Locally: Result Path

This is the shortest truthful local setup path. It starts when you are ready to install dependencies and boot the stack yourself; it is not a hosted "try now" flow.

By the end of this path, you should have:

- a local stack running
- a first queued or completed processing job
- a digest feed you can inspect
- a job page with step-level evidence

### 1. Boot the stack

```bash
./bin/sourceharbor help
cp .env.example .env
set -a
source .env
set +a
UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$SOURCE_HARBOR_CACHE_ROOT/project-venv}" \
  uv sync --frozen --extra dev --extra e2e
bash scripts/ci/prepare_web_runtime.sh >/dev/null
./bin/bootstrap-full-stack
./bin/full-stack up
source .runtime-cache/run/full-stack/resolved.env
```

Read the resolved local routes:

- API: `${SOURCE_HARBOR_API_BASE_URL}`
- Web: `http://127.0.0.1:${WEB_PORT}`

The clean local path is container-first for Postgres. By default `.env.example`
uses `CORE_POSTGRES_PORT=15432` together with
`postgresql+psycopg://postgres:postgres@127.0.0.1:${CORE_POSTGRES_PORT}/sourceharbor`
so a host Postgres on `127.0.0.1:5432` does not silently become the active data
plane.

Two local runtime layers now stay explicitly separated:

- **core stack:** Postgres + Temporal + API/Web/Worker. `./bin/bootstrap-full-stack`
  still prefers Docker-backed core services first, but it can now fall back to
  repo-owned local Postgres/Temporal under `.runtime-cache/` when Docker is
  unavailable and local `postgres` / `initdb` / `pg_ctl` / `temporal` binaries
  exist.
- **reader stack:** Miniflux + Nextflux. This stays a Docker-only optional lane
  and no longer blocks the base first-run path by default.

If you intentionally want the reader stack too, opt in:

```bash
./bin/bootstrap-full-stack --with-reader-stack 1 --reader-env-file env/profiles/reader.local.env
```

Open the operator UI at the resolved web URL:

- `http://127.0.0.1:${WEB_PORT}`

If you only need the repo-managed local proof, stop at the supervisor checks
first:

```bash
./bin/full-stack status
./bin/doctor
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/healthz"
curl -I "http://127.0.0.1:${WEB_PORT}/ops"
```

`./bin/smoke-full-stack --offline-fallback 0` is the stricter long live-smoke
lane. It goes beyond local supervisor proof and can still stop on provider-side
YouTube preflight or Resend sender configuration even after the local stack is
healthy.

### 2. Set the local write token for direct API calls

```bash
export SOURCE_HARBOR_API_KEY="${SOURCE_HARBOR_API_KEY:-sourceharbor-local-dev-token}"
```

If you launch the API outside `./bin/full-stack up`, export both
`SOURCE_HARBOR_API_KEY` and `WEB_ACTION_SESSION_TOKEN` **before** starting the
API process so write routes and web actions share the same local token contract.

When you stay on the repo-managed `./bin/full-stack up` path, SourceHarbor now
writes the local web runtime's `.env.local` inside
`.runtime-cache/tmp/web-runtime/workspace/apps/web/` so the browser bundle and
server actions both inherit the same local write-session fallback. This keeps
`CI=false` style env noise from accidentally suppressing the maintainer-local
`sourceharbor-local-dev-token` fallback.

### 3. Queue a first processing run

Replace the sample URL with any public YouTube or Bilibili video:

```bash
curl -sS -X POST "${SOURCE_HARBOR_API_BASE_URL}/api/v1/videos/process" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${SOURCE_HARBOR_API_KEY}" \
  -d '{
    "video": {
      "platform": "youtube",
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    },
    "mode": "full"
  }'
```

### 4. Inspect the resulting job and feed

```bash
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/videos" | jq
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/feed/digests" | jq
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/jobs/<job-id>" | jq
```

Open these front-door routes after the stack is up:

- `/search` for grounded search
- `/ask` for the story-aware, briefing-backed Ask front door, now sharing the same server-owned selected-story read-model that `/briefings` uses
- `/mcp` for the in-product MCP front door
- `/ops` for operator diagnostics and hardening gates

The truthful package story today is intentionally thin:

- `sourceharbor` from [`packages/sourceharbor-cli`](./packages/sourceharbor-cli/README.md) stays repo-aware and delegates to the repo-local command substrate instead of pretending to manage the whole local runtime itself
- `./bin/sourceharbor mcp` and `./bin/sourceharbor doctor` remain the repo-local operator entrypoints
- [`packages/sourceharbor-sdk`](./packages/sourceharbor-sdk/README.md) is the public TypeScript SDK surface and still stays contract-first instead of becoming a second business-logic stack
- Python SDK, Hosted, Autopilot, and plugin-market surfaces still stay later/no-go

### 5. Run the repo smoke path

```bash
./bin/smoke-full-stack --offline-fallback 0
```

When you want the operator-side log trail, start at `.runtime-cache/logs/components/full-stack`.

If you want the stricter repo-side closeout gate on a maintainer workstation,
`./bin/repo-side-strict-ci --mode pre-push` still prefers the standard-env
container path while Docker is healthy, but it now falls back to the
host-bootstrapped pre-push quality gate when the Docker daemon itself is the
only missing layer.

For a guided version with operator notes and public-proof boundaries, go to [docs/start-here.md](./docs/start-here.md).

## Why SourceHarbor Feels Different

Most repos in this space stop at one of these layers:

- a transcript extractor
- a summarizer script
- a search index
- an internal dashboard

SourceHarbor is built around the full knowledge flow:

1. **Capture** sources continuously
2. **Process** each item into job-backed artifacts
3. **Read** results in a digest feed
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

Generated docs under `docs/generated/` can point you toward runtime-owned evidence, but they are not the current verdict themselves. Historical plans under `.agents/Plans/` explain past execution context only and should not be read as the current public truth route.

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
- `apps/web`: browser command center for operators
- `contracts`: shared schemas and generated contract artifacts
- `docs`: layered public navigation, proof, and architecture

## Community

- **Questions and roadmap discussion:** [GitHub Discussions](https://github.com/xiaojiou176-open/sourceharbor/discussions)
- **Bug reports and feature requests:** [GitHub Issues](https://github.com/xiaojiou176-open/sourceharbor/issues)
- **Security reports:** [SECURITY.md](./SECURITY.md)
- **Project conduct and ownership:** [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md), [.github/CODEOWNERS](./.github/CODEOWNERS)
- **Rights and public artifact boundaries:** [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md), [docs/reference/public-artifact-exposure.md](./docs/reference/public-artifact-exposure.md)
- **Public asset provenance:** [docs/reference/public-assets-provenance.md](./docs/reference/public-assets-provenance.md)

## License

SourceHarbor is released under the MIT License. See [LICENSE](./LICENSE).
