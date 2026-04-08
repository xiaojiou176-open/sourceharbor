# SourceHarbor OpenClaw Pack

This is the first public OpenClaw local starter pack for SourceHarbor.

Use it when you want:

- the quickest OpenClaw compatibility path
- a local starter pack that points at MCP, HTTP API, CLI, and SDK
- a public OpenClaw-shaped skill without relying on repo-private `.agents/skills`

Start here:

- `docs/compat/openclaw.md`
- `starter-packs/openclaw/sourceharbor-mcp-template.json`
- `starter-packs/openclaw/openclaw.plugin.json`
- `starter-packs/openclaw/skills/sourceharbor-watchlist-briefing/SKILL.md`
- `starter-packs/openclaw/skills/sourceharbor-watchlist-briefing/references/mcp-and-http-setup.md`
- `starter-packs/openclaw/skills/sourceharbor-watchlist-briefing/references/capability-map.md`

## Three-step quickstart

1. Copy or symlink this whole directory into the local plugin or workspace-skill
   location you already use for OpenClaw.
2. Open `sourceharbor-mcp-template.json` and replace
   `__REPLACE_WITH_SOURCEHARBOR_REPO_ROOT__` with the absolute path to your
   SourceHarbor checkout.
3. Point OpenClaw at `openclaw.plugin.json`, then start with
   `skills/sourceharbor-watchlist-briefing/SKILL.md` as the first workflow.

If your local SourceHarbor stack is not using `http://127.0.0.1:9000`, replace
the placeholder with the real `SOURCE_HARBOR_API_BASE_URL` before you hand the
template to OpenClaw.

Honest boundary:

- this is a first-cut local starter pack
- it is not a registry-published OpenClaw plugin
- it is not a plugin marketplace claim
