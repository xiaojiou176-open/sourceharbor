# Public Skills And Starter Packs

SourceHarbor now has a first public starter surface for builder workflows.

Think of it like the difference between an internal workshop notebook and a public starter kit:

- `.agents/skills/**` stays internal
- `starter-packs/` is the public starter-kit directory
- `templates/public-skills/**` holds the copyable prompt/template assets those starter packs point to

## What Is Shipped Now

| Surface | What it is | Current boundary |
| --- | --- | --- |
| `docs/compat/codex.md` | shortest Codex adoption path | public, documented, reproducible |
| `docs/compat/github-copilot.md` | shortest GitHub Copilot adoption path | public, documented, reproducible |
| `docs/compat/claude-code.md` | shortest Claude Code adoption path | public, documented, reproducible |
| `docs/compat/vscode-agent.md` | shortest VS Code agent adoption path | public, documented, reproducible |
| `docs/compat/openclaw.md` + `starter-packs/openclaw/` | shortest OpenClaw local-pack path | public, first-cut, reproducible local starter pack over the same MCP / HTTP truth |
| `starter-packs/codex/sourceharbor-codex-plugin/` | Codex-compatible plugin-grade bundle | public, plugin-shaped, strongest Codex distribution artifact today |
| `starter-packs/github-copilot/sourceharbor-github-copilot-plugin/` | GitHub Copilot plugin-grade bundle | public, plugin-shaped, source-installable today |
| `starter-packs/claude-code/sourceharbor-claude-plugin/` | Claude Code plugin-grade bundle | public, plugin-shaped, submission-ready |
| `starter-packs/vscode-agent/sourceharbor-vscode-agent-plugin/` | VS Code agent plugin-grade bundle | public, plugin-shaped, source-installable today |
| `starter-packs/openclaw/clawhub.package.template.json` | OpenClaw / ClawHub package metadata template | public, publish-ready template, not a live publish receipt |
| root `pyproject.toml` + `starter-packs/mcp-registry/sourceharbor-server.template.json` | PyPI-ready MCP server package plus official MCP Registry template | public install-artifact lane plus registry template, but still not a live publish receipt |
| `config/public/mcp-directory-profile.json` + `docs/public-distribution.md` | site-specific MCP directory listing inputs and truth ledger | public distribution summary only; submit/read-back remains maintainer-managed |
| `starter-packs/**` | primary public starter-pack directory | public top-level adoption surface |
| `templates/public-skills/**` | copyable prompt/template assets referenced by the starter packs | public starter surface, not internal skill export |
| `examples/sdk/search.ts` | minimal SDK example | public example for `@sourceharbor/sdk` |
| `examples/cli/search.sh` | minimal CLI example | public example for `@sourceharbor/cli` |
| `starter-packs/openclaw/skills/**` | OpenClaw-shaped starter skill files | public starter-pack skill surface, not internal skill export |

## Skill Applicability Matrix

| Surface | Is it a public skill surface? | Why |
| --- | --- | --- |
| **Whole SourceHarbor repo** | No | the repo includes Web, API, MCP, runtime, docs, CLI, SDK, and builder packaging |
| **`starter-packs/**`** | Yes | public adoption entrypoints for Codex / GitHub Copilot / Claude Code / VS Code agent / OpenClaw / SDK workflows |
| **plugin-grade bundle directories** | Yes | the closest repo-owned artifacts to official marketplace or registry submission |
| **`templates/public-skills/**`** | Yes, as support material | copyable public prompts/templates used by the starter packs |
| **internal `.agents/skills/**`** | No | internal operating surface, not public export |

## Naming Rule

- open `starter-packs/` when you want the public entry directory
- use `templates/public-skills/**` for the copyable prompt/template files inside that starter surface
- use [`docs/public-distribution.md`](./public-distribution.md) when the question becomes official submission or listing truth

## Fastest Adoption Ladder

| I want to... | Open this first | Current truth |
| --- | --- | --- |
| drive the same operator truth from Codex | [docs/compat/codex.md](./compat/codex.md) | ship-now fit through MCP + HTTP API + CLI / SDK |
| do the same from GitHub Copilot | [docs/compat/github-copilot.md](./compat/github-copilot.md) | ship-now fit through MCP + HTTP API + CLI / SDK + source-installable plugin bundle |
| do the same from Claude Code | [docs/compat/claude-code.md](./compat/claude-code.md) | ship-now fit through MCP + HTTP API + CLI / SDK |
| do the same from VS Code agent workflows | [docs/compat/vscode-agent.md](./compat/vscode-agent.md) | ship-now fit through MCP + HTTP API + CLI / SDK + source-installable plugin bundle |
| start from typed code integration | [packages/sourceharbor-sdk/README.md](../packages/sourceharbor-sdk/README.md) | thin contract-first public SDK |
| start from shell and commands | [packages/sourceharbor-cli/README.md](../packages/sourceharbor-cli/README.md) | thin installable CLI over the same repo-owned truth |
| evaluate OpenClaw specifically | [docs/compat/openclaw.md](./compat/openclaw.md) | first-cut local starter pack today over the generic MCP / HTTP substrate |

## Start Here

| I am... | Use this first | Why |
| --- | --- | --- |
| a Codex operator | [docs/compat/codex.md](./compat/codex.md) | best path when you want MCP/API/CLI choices explained quickly |
| a GitHub Copilot operator | [docs/compat/github-copilot.md](./compat/github-copilot.md) | same story, phrased for source-installable GitHub Copilot workflows |
| a Claude Code operator | [docs/compat/claude-code.md](./compat/claude-code.md) | same story, phrased for Claude Code workflows |
| a VS Code agent operator | [docs/compat/vscode-agent.md](./compat/vscode-agent.md) | same story, phrased for VS Code agent plugin workflows |
| an OpenClaw operator | [docs/compat/openclaw.md](./compat/openclaw.md) | first-cut local starter pack, but still not a marketplace or primary front-door claim |
| a builder writing code | [packages/sourceharbor-sdk/README.md](../packages/sourceharbor-sdk/README.md) | typed HTTP integration first |
| a builder who prefers shell | [packages/sourceharbor-cli/README.md](../packages/sourceharbor-cli/README.md) | thin CLI over current HTTP contract |

## Guardrails

- Do not treat these public starter packs as proof that SourceHarbor ships a
  plugin marketplace.
- Do not treat a plugin-grade bundle, registry template, or repo-side PyPI wheel as proof of live official listing by itself.
- Do not treat the OpenClaw local pack as proof that
  SourceHarbor already ships a registry-published OpenClaw plugin.
- Do not treat these docs as a promise that every internal agent workflow is
  supported publicly.
- Do not treat this page as proof that SourceHarbor should expose a repo-root
  `SKILL.md` or behave like a single marketplace skill package.
- Keep the public surface thin: starters should point at MCP, HTTP API, CLI,
  SDK, and the existing proof surfaces instead of inventing a parallel runtime.
