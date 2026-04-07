# SourceHarbor Codex Plugin Bundle

This bundle is the strongest public Codex distribution artifact SourceHarbor can
ship today without overclaiming an official OpenAI directory listing.

Use it when you want:

- a Codex-format plugin bundle you can copy into a repo or personal marketplace
- a SourceHarbor MCP template with the repo-root placeholder already wired
- a public watchlist-briefing skill that does not depend on internal `.agents`

What is inside:

- `.codex-plugin/plugin.json`
- `.mcp.json`
- `skills/sourceharbor-watchlist-briefing/SKILL.md`

How to use it:

1. Copy this whole directory into the Codex marketplace or plugin workspace you
   already manage.
2. Replace `__REPLACE_WITH_SOURCEHARBOR_REPO_ROOT__` in `.mcp.json` with the
   absolute path to your SourceHarbor checkout.
3. Point Codex at this bundle through the official docs-supported local or repo
   marketplace path.

Honest boundary:

- this is a plugin-grade bundle for Codex-compatible distribution
- it is not proof that SourceHarbor is officially listed in the Codex Plugin Directory
- the official Codex directory exists, but public self-serve publishing is still
  not open as of the current official docs
