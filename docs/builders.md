# Build With SourceHarbor

SourceHarbor is the builder side of the same control tower.

It already exposes six real builder-facing layers:

1. **HTTP API contract** for system integrations
2. **MCP surface** for agent clients such as Codex, GitHub Copilot, Claude Code, and VS Code agent workflows
3. **Packaged public CLI** for installable command discovery
4. **Repo-local CLI/help facade** as the underlying direct substrate
5. **Public TypeScript SDK** for typed HTTP reuse
6. **Public starter packs** for reproducible Codex / GitHub Copilot / Claude Code / VS Code agent / SDK setup, plus a first-cut OpenClaw local pack

It now also exposes a seventh adoption layer:

- **Plugin-grade bundles and official-surface templates** for Codex, GitHub Copilot, Claude Code, VS Code agent workflows, OpenClaw, and the official MCP Registry path

The safest way to read this page is:

- operators use the Web command center
- builders reuse the same truth through HTTP, MCP, CLI, SDK, or starter packs
- public skill/bundle lanes are adoption surfaces inside the repo, not the whole repo identity

| Product door | Builder meaning | Current truth |
| --- | --- | --- |
| **`/subscriptions`** | intake contract over one shared template catalog | Web, API, and MCP now all point at the same strong-supported vs generalized intake split |
| **`/watchlists`** | durable tracking-object substrate | builders can treat watchlists as saved operator intent, not a temporary browser filter |
| **`/trends`** | compounder front door | repeated runs become merged stories and evidence surfaces instead of one-off search sessions |
| **`/briefings` + `/ask`** | story-aware answer/change/evidence lane | the same server-owned story payload now carries selected-story context into Ask |
| **`/mcp`** | agent-facing reuse doorway | assistants reuse the same jobs, retrieval, artifacts, and operator truth instead of a second business-logic stack |

## Skill Applicability Matrix

Use this before you describe SourceHarbor as a "skill" anything:

| Surface | Skill-repo criteria apply? | Honest wording |
| --- | --- | --- |
| **Whole repository** | No | multi-surface product repo with Web, API, MCP, runtime, CLI, SDK, and starter surfaces |
| **`starter-packs/**`** | Yes, mostly | public starter-pack and public-skill adoption layer |
| **plugin-grade bundle directories** | Yes, strongly | submission-ready or template-ready distribution artifacts |
| **`templates/public-skills/**`** | Yes, partially | copyable public prompt/template assets referenced by starter packs |
| **internal `.agents/skills/**`** | No for public use | internal operating surface, not a public export |

If a newcomer only reads the builder docs, the safe takeaway should be:

- SourceHarbor the repo is the product home for multiple surfaces
- starter packs are one adoption layer inside that repo
- internal `.agents/skills` stay internal

## Best-Fit Clients Today

| Surface | Best fit today | Why |
| --- | --- | --- |
| **Codex** | Primary fit | SourceHarbor already exposes a real MCP server plus operator-safe HTTP contracts |
| **GitHub Copilot** | Primary fit | It can reuse the same MCP and HTTP truth, and the repo now ships a real source-installable plugin bundle |
| **Claude Code** | Primary fit | Same MCP surface, same API-backed state, same retrieval and job evidence |
| **VS Code agent workflows** | Primary fit | They can reuse the same MCP and HTTP truth, and the repo now ships a real source-installable plugin bundle |
| **Repo-local CLI users** | Primary fit | `./bin/sourceharbor help` gives one discoverable facade over the real `bin/*` entrypoints without duplicating business logic |
| **Custom MCP clients** | Primary fit | `./bin/dev-mcp` starts a real FastMCP server over the current pipeline |
| **Direct HTTP builders** | Primary fit | The repo already carries a public OpenAPI contract and typed client helpers |
| **OpenHands / OpenCode** | Secondary fit | They are ecosystem-adjacent if you integrate through MCP or HTTP, but they are not the main front door today |
| **OpenClaw** | First-cut local pack fit | the repo now ships a local OpenClaw starter pack over the generic MCP / HTTP substrate, but it still is not a primary front-door label or marketplace claim |

## Builder Entry Points

### 1. HTTP API

- Contract source: [`contracts/source/openapi.yaml`](../contracts/source/openapi.yaml)
- Service entry: [`apps/api/app/main.py`](../apps/api/app/main.py)
- Start path: [`docs/start-here.md`](./start-here.md)

Representative routes:

- `GET /api/v1/subscriptions/templates`
- `POST /api/v1/videos/process`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/retrieval/search`
- `POST /api/v1/retrieval/answer/page`
- `GET /api/v1/ops/inbox`
- `GET /api/v1/watchlists`

### 2. MCP

- Quickstart: [`docs/mcp-quickstart.md`](./mcp-quickstart.md)
- Server: [`apps/mcp/server.py`](../apps/mcp/server.py)
- Local start: `./bin/dev-mcp`

Representative tools:

- `sourceharbor.jobs.get`
- `sourceharbor.jobs.compare`
- `sourceharbor.knowledge.cards.list`
- `sourceharbor.retrieval.search`
- `sourceharbor.ingest.poll`

### 3. Packaged Public CLI

If you want one installable command surface first:

```bash
npm install --global ./packages/sourceharbor-cli
cd /path/to/sourceharbor
sourceharbor help
sourceharbor mcp
```

Current truth:

- package path: [`packages/sourceharbor-cli`](../packages/sourceharbor-cli/README.md)
- it is a **thin repo-aware public wrapper**
- inside a checkout it delegates to the repo-local `bin/sourceharbor`
- it does not replace the repo-local runtime manager
- outside a checkout it falls back to public docs guidance instead of inventing a second runtime stack

### 4. Repo-Local CLI Substrate

These remain the direct command truth:

- `./bin/sourceharbor help`
- `./bin/sourceharbor bootstrap`
- `./bin/sourceharbor full-stack up`
- `./bin/sourceharbor doctor`
- `./bin/sourceharbor mcp`

The packaged CLI above does not replace this substrate. It only makes it easier
to discover and reuse.

### 5. Public TypeScript SDK

If you want a public, typed HTTP client first:

```bash
npm install ./packages/sourceharbor-sdk
```

Package path:

- [`packages/sourceharbor-sdk`](../packages/sourceharbor-sdk/README.md)

Current truth:

- it is a **thin contract-first SDK**
- it stays on top of the HTTP API contract instead of opening a second business-logic stack
- it intentionally covers the builder-facing API layer, not every web-only operator helper

### 6. Public Starter Packs

If you want public templates instead of internal raw skills:

- [`starter-packs/README.md`](../starter-packs/README.md)
- [`starter-packs/compatibility.md`](../starter-packs/compatibility.md)
- [`starter-packs/codex/AGENTS.md`](../starter-packs/codex/AGENTS.md)
- [`starter-packs/claude-code/CLAUDE.md`](../starter-packs/claude-code/CLAUDE.md)
- [`starter-packs/openclaw/README.md`](../starter-packs/openclaw/README.md)
- [`starter-packs/typescript-sdk/example.ts`](../starter-packs/typescript-sdk/example.ts)

### 7. Plugin-Grade Bundles And Official-Surface Templates

If you need artifacts closer to public distribution than a starter README, open:

- [`starter-packs/codex/sourceharbor-codex-plugin/README.md`](../starter-packs/codex/sourceharbor-codex-plugin/README.md)
- [`starter-packs/github-copilot/sourceharbor-github-copilot-plugin/README.md`](../starter-packs/github-copilot/sourceharbor-github-copilot-plugin/README.md)
- [`starter-packs/claude-code/sourceharbor-claude-plugin/README.md`](../starter-packs/claude-code/sourceharbor-claude-plugin/README.md)
- [`starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/README.md`](../starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/README.md)
- [`starter-packs/openclaw/clawhub.package.template.json`](../starter-packs/openclaw/clawhub.package.template.json)
- [`starter-packs/mcp-registry/sourceharbor-server.template.json`](../starter-packs/mcp-registry/sourceharbor-server.template.json)
- [`config/public/mcp-directory-profile.json`](../config/public/mcp-directory-profile.json)
- [`docs/public-distribution.md`](./public-distribution.md)

Current truth:

- **Codex**: the bundle is the strongest official-docs-supported distribution artifact today, but public self-serve official listing is still not open.
- **GitHub Copilot**: the repo now ships a source-installable plugin bundle over the same MCP/API truth, without pretending that a live marketplace listing already exists.
- **Claude Code**: the bundle is submission-ready for the official marketplace path, but live listing still depends on Anthropic review.
- **VS Code agent workflows**: the repo now ships a source-installable plugin bundle for agent workflows, but live Marketplace listing still remains a separate proof layer.
- **OpenClaw**: the local pack remains first-cut, while the ClawHub package template is the strongest publish-ready artifact the repo can ship today.
- **MCP**: the root Python package now produces the real `sourceharbor-mcp` install artifact, the registry template points at the PyPI identifier `sourceharbor`, and both the Official MCP Registry entry and the PyPI project already have live public read-back at `0.1.14`; the repo-controlled package line is `0.1.19`, so the remaining gap is refresh credentials, not first-time publication proof.

## Container Truth For Builders

Do not treat every container surface as builder distribution:

| Surface | Purpose | Builder-facing claim |
| --- | --- | --- |
| `infra/compose/core-services.compose.yml` | repo-local core runtime helpers | local boot aid only |
| `.devcontainer/devcontainer.json` | contributor workspace parity | development environment only |
| `ghcr.io/xiaojiou176-open/sourceharbor-api` | dedicated API image route | product-facing API container lane; the product package now reads back as `visibility: public`, but it still stays a separate API-image builder surface rather than the default install story |
| `ghcr.io/xiaojiou176-open/sourceharbor-ci-standard` | strict CI and devcontainer parity image | infrastructure image, **not** newcomer-facing product container distribution |

The actual newcomer-facing builder surfaces are MCP, HTTP API, packaged CLI,
TypeScript SDK, starter packs, and plugin-grade bundles.

## Distribution Rule

Keep the shipping language simple:

- `bundle-ready` means the artifact exists
- `submission-ready` means the repo has a real packet/template
- `listed` only means a public upstream page exists

If you need the full shipping ledger, read [`docs/public-distribution.md`](./public-distribution.md).

- **Python SDK:** later

What stays no-go this wave:

- **Plugin / marketplace positioning as the primary product label**
- **Hosted workspace claims**
- **generic autonomous agent loops**

If you want the bucketed decision ledger instead of the packaging sequence, read
[docs/reference/ecosystem-and-big-bet-decisions.md](./reference/ecosystem-and-big-bet-decisions.md).

## Risk Boundaries

These are intentionally not opened in the current builder story:

- write-capable MCP as a default public promise
- hosted SaaS claims
- generic autonomous agent loops
- plugin-first positioning

If you need the public proof boundary before integrating, read
[`docs/proof.md`](./proof.md).
