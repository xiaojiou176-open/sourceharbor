# SourceHarbor Starter Packs

These starter packs are the first public workflow surface for builders inside
SourceHarbor.
They live inside a **multi-surface product repo, not a single skill package**.

They are intentionally **not** the same thing as `.agents/skills/`.

Think of the naming this way:

- `starter-packs/` is the public entry directory
- `templates/public-skills/**` contains the copyable prompt/template assets that those starter packs reference

Use the scope boundary like this:

| Surface | What it is |
| --- | --- |
| **Whole repo** | multi-surface product repo with Web, API, MCP, runtime, CLI, SDK, and public builder layers |
| **`starter-packs/**`** | public adoption directory inside that repo |
| **plugin-grade bundle folders** | stronger submission-ready builder artifacts inside the starter-pack layer |
| **internal `.agents/skills/**`** | internal operating aids, not public starter-pack exports |

What lives here:

- public adoption paths for Codex and Claude Code
- plugin-grade Codex and Claude Code bundle directories
- reusable workflow templates built on MCP, HTTP API, and repo-local CLI
- OpenClaw starter assets plus publish-ready package metadata templates
- MCP Registry metadata templates for official registry submission prep
- examples that stay honest about sample vs live proof

## Pick The Right Pack Fast

| If you want to... | Open this first | Current truth |
| --- | --- | --- |
| drive SourceHarbor from Codex | `starter-packs/codex/AGENTS.md` | primary public pack today |
| prepare a Codex-compatible plugin bundle | `starter-packs/codex/sourceharbor-codex-plugin/` | bundle-ready local artifact today; official Codex listing still unavailable for self-serve publishing |
| drive it from Claude Code | `starter-packs/claude-code/CLAUDE.md` | primary public pack today |
| prepare a Claude Code plugin submission bundle | `starter-packs/claude-code/sourceharbor-claude-plugin/` | plugin-grade bundle today; official listing still depends on Anthropic review |
| drive it from OpenClaw | `starter-packs/openclaw/README.md` | first-cut local starter pack today over the same MCP/API path |
| prepare OpenClaw / ClawHub packaging metadata | `starter-packs/openclaw/clawhub.package.template.json` | publish-template only today; still not proof of ClawHub publication |
| prepare official MCP Registry metadata | `starter-packs/mcp-registry/README.md` | metadata template only today; still not proof of official registry publication |
| start from SDK code instead of an agent | `starter-packs/typescript-sdk/example.ts` | public example, not a full framework pack |

What does **not** live here:

- internal L1/L2 delegation rules
- repo-private `.agents/Plans` or `.runtime-cache` assumptions
- the strict CI GHCR image or devcontainer story as a public product container
- hosted/autopilot/plugin-market promises

Use these packs when you want a versionable, documented, reproducible starting point.
