# MCP Quickstart

SourceHarbor already exposes an MCP surface for agents and automation.

In plain language:

- Web is for operators
- API is the shared service contract
- MCP is the agent-facing doorway into that same system

SourceHarbor is a **multi-surface product repo, not a single skill package**.
MCP is one doorway into that repo. Public starter packs and plugin-grade skill
bundles may help builders adopt it, but they do not redefine the whole product
as one exported skill.

That same system truth now stretches across the product line:

- `/subscriptions` defines source intake through one shared template catalog
- `/watchlists` stores the tracking object
- `/trends` and `/briefings` turn repeated runs into reusable story surfaces
- `/ask` consumes that story context instead of pretending every answer starts from nowhere
- MCP reuses those same contracts for agents

This is the strongest ecosystem binding for SourceHarbor today:

- **Codex** and **Claude Code** are a real fit because they can talk through MCP or HTTP while staying source-first and local-proof-first
- **OpenHands** and **OpenCode** are worth mentioning as ecosystem neighbors, but they are not the best primary product label for this repo
- **OpenClaw** can now use a first-cut local starter pack in this repo through the same generic MCP / HTTP substrate, but it should still stay out of the primary front door and out of plugin-first positioning

If you want one packaged command surface first from inside a local checkout, run:

```bash
npm install --global ./packages/sourceharbor-cli
source .runtime-cache/run/full-stack/resolved.env
sourceharbor templates
```

If your stack is not using the repo-managed runtime snapshot, pass the real API
base URL through `SOURCE_HARBOR_API_BASE_URL` instead of assuming port `9000`.

If you are already inside the repo and only want the direct substrate, run:

```bash
./bin/sourceharbor help
```

If you specifically want the OpenClaw-facing compatibility path, start with
[docs/compat/openclaw.md](./compat/openclaw.md) and
[starter-packs/openclaw/README.md](../starter-packs/openclaw/README.md).

Container truth, kept short:

- core-services compose is for repo-local runtime helpers
- the devcontainer is for contributor workspace parity
- the strict CI GHCR image is for CI/devcontainer parity and attestation
- none of those three are the newcomer-facing product distribution story

## Start MCP Locally

```bash
./bin/bootstrap-full-stack --install-deps 0
./bin/full-stack up
source .runtime-cache/run/full-stack/resolved.env
./bin/sourceharbor mcp
```

The thin facade above routes to the same underlying entrypoint as
`./bin/dev-mcp`. This starts the FastMCP server wired in
[apps/mcp/server.py](../apps/mcp/server.py).

## Representative Tools

- `sourceharbor.jobs.get`
- `sourceharbor.jobs.compare`
- `sourceharbor.knowledge.cards.list`
- `sourceharbor.retrieval.search`
- `sourceharbor.ingest.poll`

The full manifest lives in [apps/mcp/schemas/tools.json](../apps/mcp/schemas/tools.json).

## Honest Boundary

- MCP is real and already wired
- MCP is not a second copy of the business logic
- MCP is not evidence that the whole repo should be described as a single skill package
- `@sourceharbor/cli` is a thin builder-facing wrapper over the HTTP API, and
  inside a checkout its convenience commands can delegate back into the
  repo-local substrate
- the packaged CLI reads `SOURCE_HARBOR_API_BASE_URL` from the environment
  today; it does not expose a standalone `--base-url` flag
- the public TypeScript SDK lives next to this flow in `packages/sourceharbor-sdk`; Python SDK still stays later
- advanced lanes such as UI audit and computer-use may still require extra runtime conditions or secrets

## Why It Matters

Think of MCP as the control panel for assistants:

- operators use the command center
- system integrations use the API
- agents use MCP

All three surfaces point at the same pipeline state.

If you want the honest builder-facing map instead of just the quickstart, read
[builders.md](./builders.md).
