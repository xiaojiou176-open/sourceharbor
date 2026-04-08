# Public Skills And Starter Packs

SourceHarbor now has a first public starter surface for builder workflows.

Think of it like the difference between a private workshop notebook and a
public starter kit:

- `.agents/skills/**` is still the internal workshop notebook
- `starter-packs/` is the public starter-kit directory a builder newcomer should open after choosing a Codex / Claude Code / OpenClaw-style adoption path
- `templates/public-skills/**` holds the copyable prompt/template assets that those starter packs point to
- this page and the examples below explain how those public pieces fit together

SourceHarbor is a **multi-surface product repo, not a single skill package**.
The surfaces documented here are the public starter-pack / public-skill layer
inside that repo. They do not redefine the whole repo as one skill package.

## What Is Shipped Now

| Surface | What it is | Current boundary |
| --- | --- | --- |
| `docs/compat/codex.md` | shortest Codex adoption path | public, documented, reproducible |
| `docs/compat/claude-code.md` | shortest Claude Code adoption path | public, documented, reproducible |
| `docs/compat/openclaw.md` + `starter-packs/openclaw/` | shortest OpenClaw local-pack path | public, first-cut, reproducible local starter pack over the same MCP / HTTP truth |
| `starter-packs/codex/sourceharbor-codex-plugin/` | Codex-compatible plugin-grade bundle | public, plugin-shaped, strongest Codex distribution artifact today |
| `starter-packs/claude-code/sourceharbor-claude-plugin/` | Claude Code plugin-grade bundle | public, plugin-shaped, submission-ready |
| `starter-packs/openclaw/clawhub.package.template.json` | OpenClaw / ClawHub package metadata template | public, publish-ready template, not a live publish receipt |
| `starter-packs/mcp-registry/sourceharbor-server.template.json` | official MCP Registry metadata template | public, metadata-only template, not a live registry publish receipt |
| `starter-packs/**` | primary public starter-pack directory | public top-level adoption surface |
| `templates/public-skills/**` | copyable prompt/template assets referenced by the starter packs | public starter surface, not internal skill export |
| `examples/sdk/search.ts` | minimal SDK example | public example for `@sourceharbor/sdk` |
| `examples/cli/search.sh` | minimal CLI example | public example for `@sourceharbor/cli` |
| `starter-packs/openclaw/skills/**` | OpenClaw-shaped starter skill files | public starter-pack skill surface, not internal skill export |

## Skill Applicability Matrix

| Surface | Is it a public skill surface? | Why |
| --- | --- | --- |
| **Whole SourceHarbor repo** | No | the repo includes Web, API, MCP, runtime, docs, CLI, SDK, and builder packaging |
| **`starter-packs/**`** | Yes | public adoption entrypoints for Codex / Claude Code / OpenClaw / SDK workflows |
| **plugin-grade bundle directories** | Yes | the closest repo-owned artifacts to official marketplace or registry submission |
| **`templates/public-skills/**`** | Yes, as support material | copyable public prompts/templates used by the starter packs |
| **internal `.agents/skills/**`** | No | internal operating surface, not public export |

## Why This Surface Exists

Codex and Claude Code already fit SourceHarbor through MCP + HTTP API.

The missing piece was a public first hop that does not depend on reading our
private `.agents/skills` tree. These starter packs solve that gap by giving a
newcomer:

1. the right doorway
2. the shortest command or prompt
3. the honest boundary
4. one example they can run immediately

Use the naming like this:

- open `starter-packs/` when you want the public entry directory
- use `templates/public-skills/**` when you want the copyable prompt/template files inside that starter surface
- use the plugin-grade bundle directories when you want the strongest public distribution artifacts or templates that exist today: Codex bundle-ready, Claude submission-ready, OpenClaw publish-template plus first-cut local pack, and MCP registry metadata-only
- use [`docs/public-distribution.md`](./public-distribution.md) when you want the official-surface submission ledger and the exact human-only steps

So the safe short version is:

- public starter packs and public skills are one adoption layer
- internal `.agents/skills` are a different, internal layer
- the repository itself is still the larger multi-surface product

## Fastest Adoption Ladder

| I want to... | Open this first | Current truth |
| --- | --- | --- |
| drive the same operator truth from Codex | [docs/compat/codex.md](./compat/codex.md) | ship-now fit through MCP + HTTP API + CLI / SDK |
| do the same from Claude Code | [docs/compat/claude-code.md](./compat/claude-code.md) | ship-now fit through MCP + HTTP API + CLI / SDK |
| start from typed code integration | [packages/sourceharbor-sdk/README.md](../packages/sourceharbor-sdk/README.md) | thin contract-first public SDK |
| start from shell and commands | [packages/sourceharbor-cli/README.md](../packages/sourceharbor-cli/README.md) | thin installable CLI over the same repo-owned truth |
| evaluate OpenClaw specifically | [docs/compat/openclaw.md](./compat/openclaw.md) | first-cut local starter pack today over the generic MCP / HTTP substrate |

## Start Here

| I am... | Use this first | Why |
| --- | --- | --- |
| a Codex operator | [docs/compat/codex.md](./compat/codex.md) | best path when you want MCP/API/CLI choices explained quickly |
| a Claude Code operator | [docs/compat/claude-code.md](./compat/claude-code.md) | same story, phrased for Claude Code workflows |
| an OpenClaw operator | [docs/compat/openclaw.md](./compat/openclaw.md) | first-cut local starter pack, but still not a marketplace or primary front-door claim |
| a builder writing code | [packages/sourceharbor-sdk/README.md](../packages/sourceharbor-sdk/README.md) | typed HTTP integration first |
| a builder who prefers shell | [packages/sourceharbor-cli/README.md](../packages/sourceharbor-cli/README.md) | thin CLI over current HTTP contract |

## Guardrails

- Do not treat these public starter packs as proof that SourceHarbor ships a
  plugin marketplace.
- Do not treat a plugin-grade bundle or registry template as proof of live official listing.
- Do not treat the OpenClaw local pack as proof that
  SourceHarbor already ships a registry-published OpenClaw plugin.
- Do not treat these docs as a promise that every internal agent workflow is
  supported publicly.
- Do not treat this page as proof that SourceHarbor should expose a repo-root
  `SKILL.md` or behave like a single marketplace skill package.
- Keep the public surface thin: starters should point at MCP, HTTP API, CLI,
  SDK, and the existing proof surfaces instead of inventing a parallel runtime.
